from flask import Flask, render_template_string
import psutil
import datetime

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Pitop System Information</title>
    <meta http-equiv="refresh" content="5">
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
        .progress-bar { width: 200px; background-color: #f0f0f0; }
        .progress-bar-fill { height: 20px; background-color: #4CAF50; }
    </style>
</head>
<body>
    <h1>Pitop System Information</h1>
    <h2>CPU Usage: {{ cpu_percent }}%</h2>
    <div class="progress-bar">
        <div class="progress-bar-fill" style="width:{{ cpu_percent }}%;"></div>
    </div>
    <h2>RAM Usage: {{ ram_percent }}%</h2>
    <div class="progress-bar">
        <div class="progress-bar-fill" style="width:{{ ram_percent }}%;"></div>
    </div>
    <h2>Disk Usage:</h2>
    {% for disk in disk_usage %}
        <p>{{ disk }}</p>
    {% endfor %}
    <h2>Network Usage:</h2>
    <p>{{ network_info }}</p>
    <h2>Uptime: {{ uptime }}</h2>
    <h2>Top Processes:</h2>
    <table>
        <tr>
            <th>PID</th>
            <th>Name</th>
            <th>CPU%</th>
            <th>Memory%</th>
        </tr>
        {% for process in top_processes %}
        <tr>
            <td>{{ process.pid }}</td>
            <td>{{ process.name }}</td>
            <td>{{ process.cpu_percent }}</td>
            <td>{{ process.memory_percent }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""

def get_system_info():
    cpu_percent = psutil.cpu_percent()
    ram = psutil.virtual_memory()
    disk_usage = []
    for partition in psutil.disk_partitions(all=False):
        usage = psutil.disk_usage(partition.mountpoint)
        disk_usage.append(f"{partition.device} ({partition.mountpoint}): {usage.percent}% used")
    
    net_io = psutil.net_io_counters()
    network_info = f"Sent: {net_io.bytes_sent / (1024*1024):.2f} MB, Received: {net_io.bytes_recv / (1024*1024):.2f} MB"
    
    boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.datetime.now() - boot_time
    
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        processes.append(proc.info)
    top_processes = sorted(processes, key=lambda x: x['cpu_percent'], reverse=True)[:5]
    
    return {
        'cpu_percent': cpu_percent,
        'ram_percent': ram.percent,
        'disk_usage': disk_usage,
        'network_info': network_info,
        'uptime': str(uptime).split('.')[0],  # Remove microseconds
        'top_processes': top_processes
    }

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, **get_system_info())

def run_server():
    app.run(host='0.0.0.0', port=5000, debug=False)

if __name__ == '__main__':
    run_server()