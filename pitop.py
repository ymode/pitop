import urwid
import psutil
import plotext as plt

cpu_percentages = []

def create_battery_progress_bar(battery_percentage, bar_length=20):
    if battery_percentage:
        # Choose the color based on battery level
        if battery_percentage > 65:
            color = 'high_battery'
        elif battery_percentage > 20:
            color = 'medium_battery'
        else:
            color = 'low_battery'

        # Calculate the number of "filled" characters in the bar based on battery percentage
        filled_length = int(round(bar_length * battery_percentage / 100.0))
        bar = '|' * filled_length + ' ' * (bar_length - filled_length)
        return (color, f"[{bar}] {battery_percentage}%")
    else:
        return ('normal', "[No Battery Info]")


def get_cpu_info():
    return ('normal', f"CPU Usage: {psutil.cpu_percent()}%")

def get_ram_info():
    ram = psutil.virtual_memory()
    return ('normal', f"RAM Usage: {ram.percent}%")

def get_network_info():
    net_io = psutil.net_io_counters()
    return ('normal', f"| ↑ {net_io.bytes_sent / (1024 * 1024):.2f}MB ↓ {net_io.bytes_recv / (1024 * 1024):.2f}MB")
title_columns = urwid.Columns([
    ('weight', 1, urwid.AttrMap(urwid.Text('🐍Pitop v0.1', align='left'), 'header')),
    ('weight', 2, urwid.AttrMap(urwid.Text(get_network_info(), align='right'), 'header'))
])
title_text = urwid.AttrMap(title_columns, 'header')


def get_process_list(max_processes=6):
    # Create the header row
    header = urwid.AttrMap(urwid.Columns([
        ('fixed', 25, urwid.Text('Name')),
        ('fixed', 15, urwid.Text('User')),
        ('fixed', 8, urwid.Text('PID')),
        ('fixed', 8, urwid.Text('CPU%')),
        ('fixed', 8, urwid.Text('Mem%'))
    ]), 'header')
    process_list = [header]

    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'username']):
        try:
            name = proc.info['name'][:23]  # Limit the length of the name
            pid = str(proc.info['pid'])
            cpu = str(proc.info['cpu_percent'])
            mem = "{:.2f}".format(proc.info['memory_percent'])
            user = proc.info['username'][:15]
            # Create a row for each process
            process_row = urwid.Columns([
                ('fixed', 25, urwid.Text(name)),
                ('fixed', 15, urwid.Text(user)),
                ('fixed', 8, urwid.Text(pid)),
                ('fixed', 8, urwid.Text(cpu)),
                ('fixed', 8, urwid.Text(mem))
            ])
            process_list.append(process_row)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    # Sort and return the top processes based on CPU usage
    process_list = [process_list[0]] + sorted(process_list[1:], key=lambda x: float(x.contents[2][0].get_text()[0]), reverse=True)[:max_processes]
    return process_list

def create_cpu_progress_bar(cpu_usage, bar_length=20):
    # Calculate the number of "filled" characters in the bar based on CPU usage
    filled_length = int(round(bar_length * cpu_usage / 100.0))
    bar = '|' * filled_length + ' ' * (bar_length - filled_length)

    return f"[{bar}] {cpu_usage}% CPU Util"

def create_ram_progress_bar(ram_usage, bar_length=20):
    filled_length = int(round(bar_length * ram_usage / 100.0))
    bar = '|' * filled_length + ' ' * (bar_length - filled_length)
    return f"[{bar}] {ram_usage}% RAM Util"

# In your refresh function, continue to use the updated create_cpu_progress_bar
# ...


def refresh(_loop, _data):
    
    
    # Update the CPU usage data
    cpu_usage = psutil.cpu_percent()
    cpu_percentages.append(cpu_usage)
    # Keep the list to a certain size
    if len(cpu_percentages) > 60:
        cpu_percentages.pop(0)
    
    # Update the CPU usage progress bar
    #cpu_usage = psutil.cpu_percent()
    cpu_bar = create_cpu_progress_bar(cpu_usage)
    cpu_usage_text.set_text(cpu_bar)

    ram = psutil.virtual_memory()
    ram_usage_bar = create_ram_progress_bar(ram.percent)
    ram_usage_text.set_text(ram_usage_bar)
    
    battery = psutil.sensors_battery()
    if battery:
        battery_bar = create_battery_progress_bar(battery.percent)
    else:
        battery_bar = create_battery_progress_bar(None)
    battery_text.set_text(battery_bar)
    
    cpu_text.set_text(get_cpu_info())
    ram_text.set_text(get_ram_info())
    #network_text.set_text(get_network_info())
    title_text.base_widget.contents[1] = (urwid.Text(get_network_info(), align='right'), title_text.base_widget.contents[1][1])

    # Refresh process list with a limited number of processes as Columns widgets
    process_list_items = get_process_list(max_processes=6)
    process_list.body = urwid.SimpleFocusListWalker(process_list_items)
    loop.set_alarm_in(2, refresh)

#plot cpu
plt.plotsize(60, 15)  # Adjust the plot size to fit your layout
plt.axes_color('none')  # Set the axes color to 'none' for transparency
plt.ticks_color('white')
# Define color palette
palette = [
    ('high_battery', 'dark green', ''),
    ('medium_battery', 'brown', ''),
    ('low_battery', 'dark red', ''),
    ('normal', 'white', ''),
    ('header', 'white', 'light blue'),
]

# Text widgets for system info
battery_text = urwid.Text("")
cpu_text = urwid.Text("")
ram_text = urwid.Text("")
#network_text = urwid.Text("")
cpu_usage_text = urwid.Text("")
ram_usage_text = urwid.Text("")
#title_text = urwid.AttrMap(urwid.Text("pitop v0.1", align='center'), 'header')

title_bar = urwid.AttrMap(urwid.Columns([
    ('weight', 1, urwid.Text('🐍Pitop v0.1', align='left')),
    ('weight', 2, urwid.Text(get_network_info(), align='right'))
]), 'header')

process_items = [urwid.Text("")]
process_list = urwid.ListBox(urwid.SimpleFocusListWalker(process_items))

process_list_box = urwid.BoxAdapter(process_list, height=8)

main_content_pile = urwid.Pile([
    battery_text,
    cpu_usage_text,
    ram_usage_text,
    urwid.Divider(),
    urwid.Text('Running Processes:'),
    urwid.BoxAdapter(urwid.ListBox(urwid.SimpleFocusListWalker(get_process_list())), height=8)
])

top_layout = urwid.Pile([
    title_bar,
    urwid.LineBox(main_content_pile)
])

filler = urwid.Filler(top_layout, valign='top')
#bordered_filler = urwid.LineBox(filler)

loop = urwid.MainLoop(filler, palette=palette)
loop.set_alarm_in(2, refresh)
loop.run()
