#!/usr/bin/env python3
import urwid
import psutil
import plotext as plt
import os
import signal
import time



class ProcessRow(urwid.WidgetWrap):
    def __init__(self, proc_info):
        self.proc_info = proc_info
        self.pid = proc_info['pid']
        name = proc_info['name'][:23]
        cpu = f"{proc_info['cpu_percent']:.1f}"
        mem = f"{proc_info['memory_percent']:.2f}"
        user = proc_info['username'][:15]

        # Create the columns for this row
        cols = urwid.Columns([
            ('fixed', 25, urwid.Text(name)),
            ('fixed', 15, urwid.Text(user)),
            ('fixed', 8, urwid.Text(str(self.pid))),
            ('fixed', 8, urwid.Text(cpu)),
            ('fixed', 8, urwid.Text(mem))
        ])

        # Use urwid.AttrMap to apply attributes for normal and focus states
        super().__init__(urwid.AttrMap(cols, 'normal', focus_map='highlighted'))


cpu_percentages = []
last_process_list_refresh_time = time.time()


footer_text = urwid.Text("", align='left')

def create_footer():
    # Check if the system is plugged in or if there's a battery
    battery = psutil.sensors_battery()
    if battery:
        # If the power is plugged in, show a plugged-in emoji or text
        if battery.power_plugged:
            return "🔌 Plugged In"
        else:
            # Show the battery emoji with the current battery percentage
            return f"🔋 {battery.percent}%"
    else:
        # No battery info available, perhaps this is a desktop or server
        return "⚡️ No Battery Info"

def update_footer():
    # footer text to display power information & hot keys
    footer_text.set_text((
        create_footer() + 
        "   |   Q: Quit   |   K: Kill Process"
    ))

def handle_input(key):
    if key in ('q', 'Q'):
        raise urwid.ExitMainLoop()
    elif key in ('k', 'K'):
        kill_selected_process()
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

def kill_selected_process():
    focus_widget, idx = process_list.get_focus()
    if focus_widget:
        pid = focus_widget.pid  
        try:
            os.kill(pid, signal.SIGTERM)  # Send the terminate signal to the process
            # You might need to refresh the process list to reflect the changes
        except ProcessLookupError:
            # I need to handle the case where the process is already gone
            pass
        except PermissionError:
            # I need to handle the case where the user doesn't have permission to kill the process
            pass

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


header = urwid.AttrMap(urwid.Columns([
        ('fixed', 25, urwid.Text('Name')),
        ('fixed', 15, urwid.Text('User')),
        ('fixed', 8, urwid.Text('PID')),
        ('fixed', 8, urwid.Text('CPU%')),
        ('fixed', 8, urwid.Text('Mem%'))
    ]), 'header')

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
    
    sorted_process_widgets = sorted(
        process_list,
        key=lambda x: x.proc_info['cpu_percent'],  
        reverse=True
    )
    limited_process_widgets = sorted_process_widgets[:max_processes]       
    return limited_process_widgets

process_items = urwid.SimpleFocusListWalker(get_process_list())
process_list = urwid.ListBox(process_items)

def refresh_process_list():
    # Clear the existing process list and get a new one
    del process_items[:]  # Clear the existing list
    for proc_widget in get_process_list():
        process_items.append(proc_widget)

def create_cpu_progress_bar(cpu_usage, bar_length=20):
    # Calculate the number of "filled" characters in the bar based on CPU usage
    filled_length = int(round(bar_length * cpu_usage / 100.0))
    bar = '|' * filled_length + ' ' * (bar_length - filled_length)

    return f"[{bar}] {cpu_usage}% CPU Util"

def create_ram_progress_bar(ram_usage, bar_length=20):
    filled_length = int(round(bar_length * ram_usage / 100.0))
    bar = '|' * filled_length + ' ' * (bar_length - filled_length)
    return f"[{bar}] {ram_usage}% RAM Util"


def refresh(loop, _data):
    global last_process_list_refresh_time
    # Update the CPU usage data
    cpu_usage = psutil.cpu_percent()
    cpu_percentages.append(cpu_usage)
    # Keep the list to a certain size
    if len(cpu_percentages) > 60:
        cpu_percentages.pop(0)
    
    # Update the CPU usage progress bar
    cpu_bar = create_cpu_progress_bar(cpu_usage)
    cpu_usage_text.set_text(cpu_bar)

    #Update footer
    update_footer()

    # Update RAM usage progress bar
    ram = psutil.virtual_memory()
    ram_usage_bar = create_ram_progress_bar(ram.percent)
    ram_usage_text.set_text(ram_usage_bar)

    # Refresh network info
    title_columns.base_widget.contents[1] = (urwid.Text(get_network_info(), align='right'), title_columns.base_widget.contents[1][1])
    if time.time() - last_process_list_refresh_time > 30:
        # Refresh the process list
        new_process_list_items = get_process_list(max_processes=10)
        process_list.body = urwid.SimpleFocusListWalker(new_process_list_items)
        last_process_list_refresh_time = time.time()
 
    
    # Set up the next callback for refreshing.
    loop.set_alarm_in(2, refresh)

#plot cpu
plt.plotsize(60, 15)  
plt.axes_color('none')  
plt.ticks_color('white')
#Color palette
palette = [
    ('high_battery', 'dark green', ''),
    ('medium_battery', 'brown', ''),
    ('low_battery', 'dark red', ''),
    ('normal', 'white', ''),
    ('header', 'white', 'light blue'),
    ('highlighted', 'black', 'light magenta'),
]


footer_bar = urwid.AttrMap(footer_text, 'header')
# Text widgets for system info
battery_text = urwid.Text("")
cpu_text = urwid.Text("")
ram_text = urwid.Text("")
cpu_usage_text = urwid.Text(create_cpu_progress_bar(0))
ram_usage_text = urwid.Text(create_ram_progress_bar(0))

title_bar = urwid.AttrMap(urwid.Columns([
    ('weight', 1, urwid.Text('🐍Pitop v0.1', align='left')),
    ('weight', 2, urwid.Text(get_network_info(), align='right'))
]), 'header')

#Process list ListBox here and pass it to the BoxAdapter
process_items = urwid.SimpleFocusListWalker(get_process_list())
process_list = urwid.ListBox(process_items)
process_list_box = urwid.BoxAdapter(process_list, height=10)


process_list_pile = urwid.Pile([
    header,  # This will remain static
    process_list_box,  # This will be scrollable
])

main_content_pile = urwid.Pile([
    cpu_usage_text,
    ram_usage_text,
    urwid.Divider(),
    urwid.Text('Running Processes:'),
    process_list_pile  
])

top_layout = urwid.Pile([
    title_bar,
    urwid.LineBox(main_content_pile),
    footer_bar
])

filler = urwid.Filler(top_layout, valign='top')


def main(testing=False):
    
    if testing:
        print('test successful')
        return True
    else:
        loop = urwid.MainLoop(filler, palette, unhandled_input=handle_input)
        loop.set_alarm_in(2, refresh, user_data=None)
        loop.run()
        return True


def exit_on_q(key):
    if key in ('q', 'Q'):
        raise urwid.ExitMainLoop()


if __name__ == "__main__":
    main()
