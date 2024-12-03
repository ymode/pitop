import urwid
import psutil
import datetime
import os
import sys
import logging
import getpass
import argparse
from .web_server import run_server

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

# Set up logging
logging.basicConfig(filename='pitop_debug.log', level=logging.DEBUG)

# Global variables
MAX_HISTORY = 50
cpu_history = []
memory_history = []
sort_key = 'cpu_percent'
sort_reverse = True
process_filter = ''
need_refresh = False
last_bytes_sent = 0
last_bytes_recv = 0

class ProcessRow(urwid.WidgetWrap):
    """A custom widget for displaying process information."""
    def __init__(self, proc_info):
        self.proc_info = proc_info
        self.pid = proc_info['pid']
        name = proc_info['name'][:33]
        cpu = f"{proc_info['cpu_percent']:7.1f}"
        mem = f"{proc_info['memory_percent']:7.2f}"
        user = proc_info['username'][:18]

        self.cols = urwid.Columns([
            ('fixed', 35, urwid.Text(('process', name))),
            ('fixed', 20, urwid.Text(('process', user))),
            ('fixed', 10, urwid.Text(('process', str(self.pid)))),
            ('fixed', 10, urwid.Text(('process', cpu))),
            ('fixed', 10, urwid.Text(('process', mem)))
        ])
        super().__init__(urwid.AttrMap(self.cols, 'process', focus_map='highlighted'))

    def selectable(self):
        return True

    def keypress(self, size, key):
        if key in ('up', 'down', 'page up', 'page down'):
            return key
        return key

def get_process_list(max_processes=10):
    """Get list of processes sorted by memory usage."""
    processes = []
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'username']):
            try:
                pinfo = proc.info
                if process_filter and process_filter.lower() not in pinfo['name'].lower():
                    continue
                processes.append(ProcessRow({
                    'pid': pinfo['pid'],
                    'name': pinfo['name'][:25],
                    'cpu_percent': pinfo['cpu_percent'] or 0.0,
                    'memory_percent': pinfo['memory_percent'] or 0.0,
                    'username': pinfo['username'][:15]
                }))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception as e:
        logging.error(f"Error getting process list: {e}")
        return []

    # Sort processes
    processes.sort(
        key=lambda x: getattr(x.proc_info, sort_key, 0),
        reverse=sort_reverse
    )
    
    return processes[:max_processes]

def refresh_process_list_callback(loop, user_data):
    """Refresh the process list periodically."""
    global need_refresh
    try:
        new_process_list = get_process_list(max_processes=10)
        if new_process_list:
            process_list.body[:] = new_process_list
            logging.debug(f"Process list updated with {len(new_process_list)} items")
        loop.draw_screen()
    except Exception as e:
        logging.error(f"Error in refresh_process_list_callback: {e}")
    
    loop.set_alarm_in(30, refresh_process_list_callback)

def create_progress_bar(percent, width=70):
    """Create a colored progress bar based on percentage."""
    filled = int(width * percent / 100)
    empty = width - filled
    
    # Get color based on percentage
    if percent >= 90:
        color = 'critical'
    elif percent >= 70:
        color = 'warning'
    else:
        color = 'normal'
    
    # Create the bar with proper spacing
    bar = '█' * filled + '▒' * empty
    return [
        ('normal', f"{percent:5.1f}% ["),
        (color, bar),
        ('normal', "]")
    ]

def create_mini_graph(values, width=80, height=3):
    """Create a mini ASCII graph from historical values."""
    if not values or all(v == 0 for v in values):
        return [('normal', "Collecting data...")]
    
    # Ensure we have enough values
    while len(values) < width:
        values.insert(0, 0)
    values = values[-width:]  # Only keep the last 'width' values
    
    # Normalize values to fit height
    max_val = max(values) if max(values) > 0 else 1
    normalized = [int((v / max_val) * (height * 8)) for v in values]
    
    # Block characters for different heights (8 levels per character)
    blocks = " ▁▂▃▄▅▆█"
    
    # Create the graph
    graph = []
    for i in range(width):
        val = values[i]
        norm_val = normalized[i] // 8
        remainder = normalized[i] % 8
        
        if val >= 90:
            color = 'critical'
        elif val >= 70:
            color = 'warning'
        else:
            color = 'normal'
            
        if norm_val >= height:
            graph.append((color, "█"))
        elif norm_val < 0:
            graph.append(('normal', " "))
        else:
            graph.append((color, blocks[remainder]))
    
    # Add percentage indicator on the right
    current_val = values[-1]
    graph.extend([
        ('normal', f" {current_val:5.1f}%")
    ])
    
    return graph

def get_battery_info():
    """Get detailed battery information."""
    try:
        battery = psutil.sensors_battery()
        if battery:
            percent = battery.percent
            charging = battery.power_plugged
            time_left = ""
            if battery.secsleft > 0:
                hours = battery.secsleft // 3600
                minutes = (battery.secsleft % 3600) // 60
                time_left = f" ({hours:02d}:{minutes:02d})"
            
            icon = "⚡" if charging else "🔋"
            color = 'normal' if percent > 30 else 'critical'
            return [(color, f"{icon} {percent}%{time_left}")]
        return [('normal', "⚡ AC Power")]
    except Exception as e:
        logging.error(f"Error getting battery info: {e}")
        return [('normal', "⚡ AC Power")]

def get_uptime():
    """Get the system uptime in a nicely formatted string."""
    boot_time = psutil.boot_time()
    now = datetime.datetime.now()
    uptime = now - datetime.datetime.fromtimestamp(boot_time)
    
    days = uptime.days
    hours = uptime.seconds // 3600
    minutes = (uptime.seconds % 3600) // 60
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    
    return "⏱️ " + " ".join(parts)

def get_network_text(sent_rate, recv_rate):
    """Get colored network rate text based on thresholds."""
    def get_rate_color(rate):
        if rate > 1024:  # More than 1 MB/s
            return 'critical'
        elif rate > 512:  # More than 512 KB/s
            return 'warning'
        return 'normal'
    
    # Format rates with appropriate units
    def format_rate(rate):
        if rate > 1024:
            return f"{rate/1024:.1f}MB/s"
        return f"{rate:.1f}KB/s"
    
    sent_color = get_rate_color(sent_rate)
    recv_color = get_rate_color(recv_rate)
    
    return [
        ('bold', "Network: "),
        ('normal', "⬆️ "),
        (sent_color, format_rate(sent_rate)),
        ('normal', "  ⬇️ "),
        (recv_color, format_rate(recv_rate))
    ]

def update_system_info(loop, user_data):
    """Update all system information displayed in the UI."""
    global cpu_history, memory_history, need_refresh
    
    try:
        # Update time
        current_time = datetime.datetime.now()
        header_time.set_text(current_time.strftime("%Y-%m-%d %H:%M:%S"))
        
        # Update uptime with bold label
        uptime_widget.set_text([('bold', "Uptime: "), ('normal', get_uptime())])
        
        # Update network usage
        net_io = psutil.net_io_counters()
        bytes_sent = net_io.bytes_sent
        bytes_recv = net_io.bytes_recv
        
        if not hasattr(update_system_info, 'last_bytes_sent'):
            update_system_info.last_bytes_sent = bytes_sent
            update_system_info.last_bytes_recv = bytes_recv
        
        # Calculate rates
        sent_rate = (bytes_sent - update_system_info.last_bytes_sent) / 1024  # KB/s
        recv_rate = (bytes_recv - update_system_info.last_bytes_recv) / 1024  # KB/s
        
        # Update last values
        update_system_info.last_bytes_sent = bytes_sent
        update_system_info.last_bytes_recv = bytes_recv
        
        # Set colored network text
        network_widget.set_text(get_network_text(sent_rate, recv_rate))
        
        # Get system stats
        cpu_percent = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        
        # Update history
        cpu_history.append(cpu_percent)
        memory_history.append(ram.percent)
        if len(cpu_history) > MAX_HISTORY:
            cpu_history = cpu_history[-MAX_HISTORY:]
        if len(memory_history) > MAX_HISTORY:
            memory_history = memory_history[-MAX_HISTORY:]
        
        # Create CPU display
        cpu_text = [('bold', "CPU: ")]
        cpu_text.extend(create_progress_bar(cpu_percent))
        cpu_bar.set_text(cpu_text)
        
        # Create RAM display
        ram_text = [('bold', "RAM: ")]
        ram_text.extend(create_progress_bar(ram.percent))
        ram_bar.set_text(ram_text)
        
        # Update graphs
        cpu_graph_widget.set_text(create_mini_graph(cpu_history))
        memory_graph_widget.set_text(create_mini_graph(memory_history))
        
        # Update battery info
        battery = get_battery_info()
        if battery:
            battery_widget.set_text(battery)
        
        # Update disk info
        disk_parts = []
        for part in psutil.disk_partitions(all=False):
            if os.name == 'nt' and ('cdrom' in part.opts or part.fstype == ''):
                continue
            usage = psutil.disk_usage(part.mountpoint)
            if part.mountpoint == '/':  # Only show root partition
                disk_parts.append(f"Disk Usage: {usage.used//(1024**3)}GB / {usage.total//(1024**3)}GB ({usage.percent}%)")
        disk_info_text.set_text("\n".join(disk_parts))
        
        # Update process list if needed
        if need_refresh:
            process_list.body[:] = get_process_list()
            need_refresh = False
            
    except Exception as e:
        logging.error(f"Error in update_system_info: {e}")
    
    loop.set_alarm_in(1, update_system_info)

def exit_filter_mode(button):
    """Exit the process filter mode."""
    urwid.MainLoop.get_current().widget = frame

def on_filter_change(edit, new_text):
    """Handle changes to the process filter."""
    global process_filter, need_refresh
    process_filter = new_text
    need_refresh = True

def handle_input(key):
    """Handle keyboard input."""
    global sort_key, sort_reverse, process_filter, need_refresh
    if key in ('q', 'Q'):
        raise urwid.ExitMainLoop()
    elif key in ('k', 'K'):
        kill_selected_process()
    elif key in ('c', 'C'):  # Sort by CPU
        if sort_key == 'cpu_percent':
            sort_reverse = not sort_reverse
        else:
            sort_key = 'cpu_percent'
            sort_reverse = True
        need_refresh = True
    elif key in ('m', 'M'):  # Sort by Memory
        if sort_key == 'memory_percent':
            sort_reverse = not sort_reverse
        else:
            sort_key = 'memory_percent'
            sort_reverse = True
        need_refresh = True
    elif key in ('p', 'P'):  # Sort by PID
        if sort_key == 'pid':
            sort_reverse = not sort_reverse
        else:
            sort_key = 'pid'
            sort_reverse = True
        need_refresh = True
    elif key in ('/', '?'):  # Enter filter mode
        urwid.MainLoop.get_current().widget = filter_overlay
    elif key == 'esc':  # Clear filter
        process_filter = ''
        need_refresh = True
    return key

def kill_selected_process():
    """Kill the selected process."""
    focus = process_list.focus
    if focus is not None:
        pid = focus.pid
        try:
            process = psutil.Process(pid)
            process.terminate()
            logging.debug(f"Process with PID {pid} terminated.")
        except psutil.NoSuchProcess:
            logging.debug(f"No process found with PID {pid}")
        except psutil.AccessDenied:
            logging.debug(f"Access denied when trying to terminate process with PID {pid}")
        global need_refresh
        need_refresh = True

def load_palette_config():
    """Load the color palette configuration from the TOML file."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(current_dir, 'pitop.toml')
    
    try:
        with open(config_path, 'rb') as f:
            config = tomllib.load(f)
    except (FileNotFoundError, tomllib.TOMLDecodeError) as e:
        logging.error(f"Error loading configuration file: {e}")
        return [
            ('header', 'white', 'dark blue'),
            ('footer', 'white', 'dark blue'),
            ('body', 'white', 'black'),
            ('bold', 'white,bold', 'black'),
            ('process', 'light gray', 'black'),
            ('highlighted', 'black', 'light gray'),
            ('normal', 'light green', 'black'),
            ('warning', 'yellow', 'black'),
            ('critical', 'light red', 'black'),
        ]

    return [
        ('header', config['palette']['header_fg'], config['palette']['header_bg']),
        ('footer', config['palette']['footer_fg'], config['palette']['footer_bg']),
        ('body', config['palette']['body_fg'], config['palette']['body_bg']),
        ('bold', 'white,bold', 'black'),
        ('process', 'light gray', 'black'),
        ('highlighted', config['palette']['highlighted_fg'], config['palette']['highlighted_bg']),
        ('normal', config['palette']['normal_fg'], config['palette']['normal_bg']),
        ('warning', config['palette']['warning_fg'], config['palette']['warning_bg']),
        ('critical', config['palette']['critical_fg'], config['palette']['critical_bg']),
    ]

# Initialize widgets
header_time = urwid.Text("", align='right')
header = urwid.Columns([
    ('weight', 2, urwid.Text("Pitop")),
    ('weight', 3, header_time),
    ('weight', 1, urwid.Text("CPU"))
])
header = urwid.AttrMap(header, 'header')

# Create widgets
cpu_bar = urwid.Text("")
ram_bar = urwid.Text("")
cpu_graph_widget = urwid.Text("")
memory_graph_widget = urwid.Text("")
battery_widget = urwid.Text("")
disk_info_text = urwid.Text("")
uptime_widget = urwid.Text("")
network_widget = urwid.Text("")

# Process list headers
column_headers = urwid.AttrMap(urwid.Columns([
    ('fixed', 35, urwid.Text('Name')),
    ('fixed', 20, urwid.Text('User')),
    ('fixed', 10, urwid.Text('PID')),
    ('fixed', 10, urwid.Text('CPU%')),
    ('fixed', 10, urwid.Text('MEM%'))
]), 'header')

# Process list
process_items = urwid.SimpleFocusListWalker([])
process_list = urwid.ListBox(process_items)

# Stats section
stats_pile = urwid.Pile([
    urwid.Text(""),  # Spacer
    cpu_bar,
    ram_bar,
    urwid.Text(""),  # Spacer for separation
    uptime_widget,  # Add uptime widget
    network_widget,  # Add network widget
    urwid.Text(""),  # Spacer
])

# Main layout
body_content = urwid.Pile([
    ('pack', header),
    ('pack', urwid.AttrMap(urwid.Divider('─'), 'header')),
    ('pack', battery_widget),
    ('pack', stats_pile),
    ('pack', urwid.AttrMap(urwid.Divider('─'), 'header')),
    ('pack', urwid.AttrMap(urwid.Text(" CPU History"), 'header')),
    ('pack', urwid.LineBox(cpu_graph_widget)),
    ('pack', urwid.AttrMap(urwid.Text(" Memory History"), 'header')),
    ('pack', urwid.LineBox(memory_graph_widget)),
    ('pack', urwid.AttrMap(urwid.Divider('─'), 'header')),
    ('pack', column_headers),
    ('weight', 1, urwid.LineBox(process_list)),
    ('pack', urwid.AttrMap(urwid.Divider('─'), 'header')),
    ('pack', disk_info_text)
])

# Main frame
frame = urwid.Frame(
    urwid.AttrMap(body_content, 'body'),
    footer=urwid.AttrMap(
        urwid.Text("Q:Quit  K:Kill  C:Sort CPU  M:Sort Memory  P:Sort PID  /:Filter  ESC:Clear Filter", align='center'),
        'footer'
    )
)

# Create filter overlay
filter_edit = urwid.Edit("Filter: ")
urwid.connect_signal(filter_edit, 'change', on_filter_change)
filter_done = urwid.Button("Done")
urwid.connect_signal(filter_done, 'click', exit_filter_mode)
filter_pile = urwid.Pile([filter_edit, filter_done])
filter_overlay = urwid.Overlay(
    urwid.LineBox(filter_pile),
    frame,
    'center', 30,
    'middle', 5
)

def main(testing=False):
    """Main function to run the application."""
    global process_list, frame, cpu_history, memory_history
    
    try:
        if testing:
            return True
            
        # Initialize histories
        cpu_history = []
        memory_history = []
        
        # Load color palette
        palette = load_palette_config()
        
        # Initialize process list
        initial_processes = get_process_list(max_processes=10)
        process_items = urwid.SimpleFocusListWalker(initial_processes)
        process_list.body[:] = process_items
        
        # Create and run the main loop
        loop = urwid.MainLoop(frame, palette=palette, unhandled_input=handle_input)
        loop.set_alarm_in(1, update_system_info)
        loop.set_alarm_in(30, refresh_process_list_callback)
        loop.run()
        
    except Exception as e:
        logging.error(f"Error in main: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pitop System Monitor")
    parser.add_argument("--web", action="store_true", help="Run web server instead of TUI")
    args = parser.parse_args()

    if args.web:
        run_server()
    else:
        main() 