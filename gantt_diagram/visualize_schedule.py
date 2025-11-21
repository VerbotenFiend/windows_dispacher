import matplotlib.pyplot as plt
import matplotlib.patches as patches
import sys
import re

def parse_output(filename):
    data = {
        'cpu': {},      # pid -> list of (start, duration)
        'io': {},       # pid -> list of (start, duration)
        'ready': {},    # time -> list of pids
        'events': {},   # time -> list of event descriptions
        'max_time': 0,
        'pids': set()
    }
    
    current_time = 0
    
    with open(filename, 'r') as f:
        lines = f.readlines()
        
    # Regex patterns
    time_pattern = re.compile(r'\*+ TIME: (\d+) \*+')
    running_pattern = re.compile(r'\s*running pid:\s*(\d+)')
    waiting_pattern = re.compile(r'\s*waiting pid:\s*(\d+)')
    ready_pattern = re.compile(r'\s*ready pid:\s*(\d+)')
    
    # Temporary state for current tick
    current_running = -1
    current_waiting = []
    current_ready = []
    
    for line in lines:
        time_match = time_pattern.search(line)
        if time_match:
            # Process previous tick's data
            if current_time > 0: # Skip initial 0 state if empty or handle it
                pass
                
            # Start new tick
            current_time = int(time_match.group(1))
            data['max_time'] = max(data['max_time'], current_time)
            
            # Reset per-tick state
            current_waiting = []
            current_ready = []
            current_running = -1
            continue
            
        run_match = running_pattern.search(line)
        if run_match:
            pid = int(run_match.group(1))
            if pid != -1:
                current_running = pid
                data['pids'].add(pid)
                if pid not in data['cpu']: data['cpu'][pid] = []
                # Add 1 unit of CPU time at current_time
                # We merge contiguous blocks later or draw 1-unit blocks
                data['cpu'][pid].append(current_time)
            continue
            
        wait_match = waiting_pattern.search(line)
        if wait_match:
            pid = int(wait_match.group(1))
            current_waiting.append(pid)
            data['pids'].add(pid)
            if pid not in data['io']: data['io'][pid] = []
            data['io'][pid].append(current_time)
            continue
            
        ready_match = ready_pattern.search(line)
        if ready_match:
            pid = int(ready_match.group(1))
            current_ready.append(pid)
            data['pids'].add(pid)
            continue
            
        # Store ready queue state for this tick (after reading all lines for the tick)
        # This is tricky because we read line by line. 
        # Actually, we should store the ready queue when we hit the NEXT time marker or EOF.
        # But for simplicity, let's assume the ready lines come before the next time marker.
        # We'll accumulate them in a dict keyed by time.
        
        # Since we can't easily know when a tick "ends" until the next starts, 
        # we might need a slightly different approach or just accept we populate 'ready' incrementally.
        if ready_match:
            if current_time not in data['ready']: data['ready'][current_time] = []
            if pid not in data['ready'][current_time]:
                data['ready'][current_time].append(pid)

    return data

def draw_gantt(data, output_file):
    pids = sorted(list(data['pids']))
    if not pids:
        print("No processes found.")
        return

    # Calculate max queue depth for the 3rd subplot height
    max_queue_depth = 0
    for t in data['ready']:
        max_queue_depth = max(max_queue_depth, len(data['ready'][t]))
    max_queue_depth = max(max_queue_depth, 1) # At least 1 to avoid singular matrix if empty

    # Adjust figure height based on content
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 10), sharex=True, 
                                        gridspec_kw={'height_ratios': [len(pids), len(pids), max_queue_depth]})
    
    max_t = data['max_time'] + 2
    
    # Common styling
    for ax in (ax1, ax2, ax3):
        ax.set_xticks(range(0, max_t + 1, 1)) # Grid line for every tick
        ax.grid(True, axis='x', which='both', linestyle='-', alpha=0.5, color='gray')
        ax.grid(True, axis='y', which='both', linestyle='-', alpha=0.5, color='gray')
        ax.set_xlim(0, max_t)
        ax.tick_params(axis='x', labelsize=6) # Reduce x-axis label size

    # 1. CPU Usage
    ax1.set_title('CPU Usage')
    ax1.set_ylabel('PID')
    ax1.set_yticks(pids)
    ax1.set_ylim(min(pids)-0.5, max(pids)+0.5)
    ax1.invert_yaxis() # PID 1 at top
    
    for pid in pids:
        if pid in data['cpu']:
            for t in data['cpu'][pid]:
                rect = patches.Rectangle((t, pid-0.4), 1, 0.8, linewidth=1, edgecolor='black', facecolor='#4CAF50') # Green
                ax1.add_patch(rect)

    # 2. I/O Usage
    ax2.set_title('I/O Usage')
    ax2.set_ylabel('PID')
    ax2.set_yticks(pids)
    ax2.set_ylim(min(pids)-0.5, max(pids)+0.5)
    ax2.invert_yaxis() # PID 1 at top
    
    for pid in pids:
        if pid in data['io']:
            for t in data['io'][pid]:
                rect = patches.Rectangle((t, pid-0.4), 1, 0.8, linewidth=1, edgecolor='black', facecolor='#F44336') # Red
                ax2.add_patch(rect)

    # 3. Ready Queue
    ax3.set_title('Ready Queue')
    ax3.set_ylabel('Queue Position')
    ax3.set_yticks(range(max_queue_depth))
    ax3.set_yticklabels([str(i+1) for i in range(max_queue_depth)])
    ax3.set_ylim(-0.5, max_queue_depth-0.5)
    ax3.invert_yaxis() # Position 1 at top
    
    for t in range(max_t):
        if t in data['ready']:
            q_list = data['ready'][t]
            for i, pid in enumerate(q_list):
                # Draw box for each process in queue
                # i is the position (0 is top/front)
                rect = patches.Rectangle((t, i-0.4), 1, 0.8, linewidth=1, edgecolor='black', facecolor='#FFC107') # Amber
                ax3.add_patch(rect)
                ax3.text(t + 0.5, i, f"P{pid}", ha='center', va='center', fontsize=8, fontweight='bold')

    plt.xlabel('Time (Ticks)')
    plt.tight_layout()
    plt.savefig(output_file)
    print(f"Gantt chart saved to {output_file}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python visualize_schedule.py <output_file>")
        sys.exit(1)
        
    input_file = sys.argv[1]
    data = parse_output(input_file)
    # Default output in gantt_diagram folder
    output_file = 'gantt_diagram/schedule.png'
    draw_gantt(data, output_file)
