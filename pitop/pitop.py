import urwid
import psutil
import datetime

global process_list
global last_bytes_sent
global last_bytes_recv 
global horizontal_line

last_bytes_sent = 0
last_bytes_recv = 0
horizontal_line = urwid.Divider(div_char='═')
#------------------------------------------------------------------------#

class ProcessRow(urwid.WidgetWrap):
    def __init__(self, proc_info):
        self.proc_info = proc_info
        self.pid = proc_info['pid']
        name = proc_info['name'][:23]
        
        # Handle the case where cpu_percent is None
        cpu_percent = proc_info.get('cpu_percent')
        if cpu_percent is not None:
            cpu = f"{cpu_percent:.1f}"
        else:
            cpu = "N/A"  
        
        mem = f"{proc_info['memory_percent']:.2f}"
        user = proc_info['username'][:15]

        self.cols = urwid.Columns([
            ('fixed', 25, urwid.Text(name)),
            ('fixed', 15, urwid.Text(user)),
            ('fixed', 8, urwid.Text(str(self.pid))),
            ('fixed', 8, urwid.Text(cpu)),
            ('fixed', 8, urwid.Text(mem))
        ])
        super().__init__(urwid.AttrMap(self.cols, 'normal', focus_map='highlighted'))

def handle_input(key):
    if key in ('q', 'Q'):
        raise urwid.ExitMainLoop()
    elif key in ('k', 'K'):
        pass#kill_selected_process()
    elif key == 'up':
        # Scroll up
        focus_position = process_list.focus_position
        if focus_position > 0:
            process_list.set_focus(focus_position - 1)
    elif key == 'down':
        # Scroll down
        focus_position = process_list.focus_position
        try:
            process_list.set_focus(focus_position + 1)
        except IndexError:
            #end of the list don't scroll
            pass

def get_uptime():
    boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
    now = datetime.datetime.now()
    uptime_seconds = (now - boot_time).total_seconds()
    hours, remainder = divmod(int(uptime_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:04d}:{minutes:02d}:{seconds:02d}"

# Function to get hours since boot
def get_hours_since_boot():
    boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
    now = datetime.datetime.now()
    return int((now - boot_time).total_seconds() // 3600)

def get_network_info():
    global last_bytes_sent, last_bytes_recv
    net_io = psutil.net_io_counters()
    
    # Calculate the difference in bytes sent/received since the last check
    bytes_sent_diff = net_io.bytes_sent - last_bytes_sent
    bytes_recv_diff = net_io.bytes_recv - last_bytes_recv
    
    # Update the last network IO counters
    last_bytes_sent = net_io.bytes_sent
    last_bytes_recv = net_io.bytes_recv
    
    # Convert to kilobytes for readability
    kb_sent_diff = bytes_sent_diff / 1024
    kb_recv_diff = bytes_recv_diff / 1024
    
    return ('', f"│↑ {kb_sent_diff:.2f} kb│↓ {kb_recv_diff:.2f} kb│")

def get_usernames():
    users = psutil.users()
    usernames = [user.name for user in users]
    return ', '.join(set(usernames))

def get_process_list(max_processes=10):
    process_list = []

    # Retrieve the process information and create a ProcessRow for each
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'username']):
        try:
            proc_info = {
                'pid': proc.info['pid'],
                'name': proc.info['name'],
                'cpu_percent': proc.info['cpu_percent'],
                'memory_percent': proc.info['memory_percent'],
                'username': proc.info['username']
            }
            process_list.append(ProcessRow(proc_info))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    # Now sorting by RAM utilization instead of CPU utilization
    sorted_process_widgets = sorted(
        process_list,
        key=lambda x: x.proc_info['memory_percent'],  # Sort by RAM usage
        reverse=True  # High to low
    )
    limited_process_widgets = sorted_process_widgets[:max_processes]       
    return limited_process_widgets



def refresh_process_list():
    global process_items  # If necessary, depending on your scope management
    new_process_list = get_process_list(max_processes=10)
    process_items.clear()
    process_items.extend(new_process_list)

def get_battery_info():
    battery = psutil.sensors_battery()
    if battery:
        # If we can get the battery information, return the percentage and a battery emoji
        percent = f"{battery.percent}%"
        if battery.power_plugged:
            # If it's charging/plugged in, show a lightning bolt
            return f"⚡ {percent}"
        else:
            # Otherwise, just show the battery percentage
            return f"🔋 {percent}"
    else:
        # If battery information is not available, assume it's plugged in
        return "⚡ Plugged In"

def update_footer_text():
    network_info = 'Network' + ''.join(get_network_info()) + " Q:Quit"
    network_footer_text.set_text(network_info)
    battery_info = get_battery_info()
    battery_footer_text.set_text(battery_info)
    footer_content = f"{battery_info} | {network_info}"
    footer_text.set_text(footer_content)

def update_system_info(loop, data):
    # Update CPU, RAM, uptime, and network info every second
    cpu_bar_markup = create_cpu_progress_bar()
    cpu_progress_bar_text.set_text(cpu_bar_markup)
    ram_bar_markup = create_ram_progress_bar()
    ram_progress_bar_text.set_text(ram_bar_markup)
    uptime_text.set_text('Uptime:' + get_uptime())
    update_footer_text()
    loop.set_alarm_in(1, update_system_info)


def refresh_process_list_callback(loop, data):
    # Refresh process list every 30 seconds
    refresh_process_list()
    loop.set_alarm_in(30, refresh_process_list_callback)

def create_cpu_progress_bar(bar_length=20):
    cpu_usage = psutil.cpu_percent(interval=None)
    filled_length = int(round(bar_length * cpu_usage / 100.0))
    filled_bar = [('progress_bar_filled', '█' * filled_length)]
    unfilled_bar = [('progress_bar_empty', '░' * (bar_length - filled_length))]
    return filled_bar + unfilled_bar + [('normal', f" {cpu_usage}% CPU Usage")]

def create_ram_progress_bar(bar_length=20):
    mem = psutil.virtual_memory()
    ram_usage = mem.percent
    filled_length = int(round(bar_length * ram_usage / 100.0))
    filled_bar = [('progress_bar_filled', '█' * filled_length)]
    unfilled_bar = [('progress_bar_empty', '░' * (bar_length - filled_length))]
    return filled_bar + unfilled_bar + [('normal', f" {ram_usage}% RAM Usage")]





# Text widget for the title
title_text = urwid.Text("🐍" + get_usernames()+" @ Ƥitop.v0.2a", align='left')
uptime_text = urwid.Text('Uptime:....' , align='left')
cpu_text = urwid.Text(' │ CPUs:' + str(psutil.cpu_count()), align='left')

#Title Bar Widget
title_bar = urwid.AttrMap(urwid.Columns([
    ('weight', 0.70, title_text),  # The title text gets twice the space
    ('weight', 0.20, uptime_text), # Uptime text gets standard space
    ('weight', 0.15, cpu_text)     # CPU text gets standard space
], dividechars=1), 'header')

#Body
cpu_progress_bar_text = urwid.Text(create_cpu_progress_bar(), align='left')
ram_progress_bar_text = urwid.Text(create_ram_progress_bar(), align='left')

progress_bars = urwid.Columns([
    ('weight', 1, cpu_progress_bar_text),
    ('weight', 1, ram_progress_bar_text)
])

process_items = urwid.SimpleFocusListWalker(get_process_list(max_processes=10))
process_list = urwid.ListBox(process_items)
column_headers = urwid.Columns([
    ('fixed', 25, urwid.Text('Name')),
    ('fixed', 15, urwid.Text('User')),
    ('fixed', 8, urwid.Text('PID')),
    ('fixed', 8, urwid.Text('CPU%')),
    ('fixed', 8, urwid.Text('MEM%'))
])

#Footer
battery_footer_text = urwid.Text("", align='left')
network_footer_text = urwid.Text("", align='center')
network_info_initial = 'Network' + ' '.join(get_network_info())
footer_text = urwid.Text(network_info_initial + " Q:Quit", align='right')

footer_bar = urwid.AttrMap(urwid.Columns([
    ('weight', 1, battery_footer_text),
    ('weight', 1, network_footer_text),
], dividechars=1), 'footer')

body_content = urwid.Pile([
    ('pack', progress_bars),
    ('pack', urwid.AttrMap(column_headers, 'header')),
    process_list,
    ('pack', horizontal_line)
    
])

frame = urwid.Frame(header=title_bar, body=body_content, footer=footer_bar)



# Create the MainLoop with the main_layout as the top widget
loop = urwid.MainLoop(frame, palette = [
    ('header', 'white', 'light blue'),
    ('footer', 'white', 'light blue'),
    #('progress_bar_filled', 'black', 'light green'),  # Foreground, Background for filled part
    #('progress_bar_empty', 'black', 'dark gray'),  # Foreground, Background for empty part
    ('highlighted', 'black', 'light magenta'),
    #('normal', 'white', 'black')  # You might need to add this for the percentage text
],
unhandled_input=handle_input)
loop.set_alarm_in(1, update_system_info) 
loop.set_alarm_in(30, refresh_process_list_callback)
# Run the loop
loop.run()