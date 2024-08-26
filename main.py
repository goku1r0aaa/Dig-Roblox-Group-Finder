import requests
import time
import os
import pyfiglet
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock, Thread
from queue import Queue
from itertools import cycle

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def display_banner():
    clear_screen()
    columns, rows = shutil.get_terminal_size()
    ascii_text = pyfiglet.figlet_format("RINA CHUPAMELA PORFA", font="standard")
    lines = ascii_text.split("\n")
    x = int(columns / 2 - len(max(lines, key=len)) / 2)
    y_positions = [int(rows / 2 - len(lines) / 2 + i) for i in range(len(lines))]
    
    print("\033[1m\033[32m", end="")
    for i, line in enumerate(lines):
        print(f"\033[{y_positions[i]};{x}H{line}")
    print("\033[1m\033[35m", end="")
    print(f"\033[{y_positions[-1] + 1};{x};{x}Â© @BABYMETAL")
    print("\033[0m", end="")

def send_webhook_message(webhook_url, message):
    data = {"content": message}
    try:
        requests.post(webhook_url, json=data)
    except requests.RequestException as e:
        print(f"Failed to send webhook message: {e}")

def load_proxies_from_file(filename):
    with open(filename, 'r') as file:
        return [line.strip() for line in file]

def get_group_statuses(group_ids, proxy, retries=3):
    group_ids_str = ",".join(map(str, group_ids))
    url = f"https://groups.roblox.com/v2/groups?groupIds={group_ids_str}"
    
    for attempt in range(retries):
        try:
            response = requests.get(url, proxies={"http": proxy, "https": proxy}, timeout=5)
            if response.status_code == 200:
                group_data_list = response.json().get('data', [])
                return {group_data.get('id'): 'ownerless' if group_data.get('owner') is None else 'owned' 
                        for group_data in group_data_list}
            else:
                time.sleep(2 ** attempt)  # Exponential backoff
        except requests.RequestException as e:
            print(f"Error fetching group statuses (Attempt {attempt + 1}/{retries}): {e}")
    
    return {}

def check_group_public_entry(group_id, proxy, retries=3):
    url = f"https://groups.roblox.com/v1/groups/{group_id}"
    
    for attempt in range(retries):
        try:
            response = requests.get(url, proxies={"http": proxy, "https": proxy}, timeout=5)
            if response.status_code == 200:
                group_data = response.json()
                return group_data.get('publicEntryAllowed', False)
            else:
                time.sleep(2 ** attempt)  # Exponential backoff
        except requests.RequestException as e:
            print(f"Error checking public entry (Attempt {attempt + 1}/{retries}): {e}")
    
    return False

def check_group_status(batch_group_ids, webhook_url, proxy, lock, count_queue):
    statuses = get_group_statuses(batch_group_ids, proxy)
    
    with lock:
        count_queue.put(len(batch_group_ids))  # Increment scan count
    
    for group_id, status in statuses.items():
        if status == 'ownerless':
            is_public_entry_allowed = check_group_public_entry(group_id, proxy)
            if is_public_entry_allowed:
                message = f"Group https://roblox.com/groups/{group_id} is ownerless and has public entry allowed."
                print(message)
                send_webhook_message(webhook_url, message)
            else:
                print(f"Group ID: {group_id} is ownerless but public entry is not allowed.")
        else:
            print(f"Group ID: {group_id} is owned or locked.")
        time.sleep(0.01)

def stat_updater(count_queue):
    counts_per_minute = []
    
    while True:
        while not count_queue.empty():
            counts_per_minute.append((time.time(), count_queue.get()))
        
        now = time.time()
        counts_per_minute = [(timestamp, count) for timestamp, count in counts_per_minute if now - timestamp <= 60]
        total_count = sum(count for _, count in counts_per_minute)
        
        print(f"[+] Checks Per Minute: {total_count:,}", end="\r")
        time.sleep(0.10)

def main():
    display_banner()
    
    start_id = 14076500
    end_id = 14700000
    webhook_url = input("Enter the webhook URL: ")
    proxy_file = "proxies.txt"
    threads_per_proxy = int(input("Enter the number of threads per proxy: "))
    
    proxies = load_proxies_from_file(proxy_file)
    proxy_pool = cycle(proxies)
    lock = Lock()
    count_queue = Queue()
    batch_size = 100
    
    # Start the stat updater thread
    stat_thread = Thread(target=stat_updater, args=(count_queue,))
    stat_thread.daemon = True
    stat_thread.start()
    
    group_ids = list(range(start_id, end_id + 1))
    
    with ThreadPoolExecutor(max_workers=threads_per_proxy * len(proxies)) as executor:
        futures = [
            executor.submit(
                check_group_status, group_ids[i:i + batch_size], webhook_url, next(proxy_pool), lock, count_queue
            )
            for i in range(0, len(group_ids), batch_size)
        ]
        
        for future in as_completed(futures):
            future.result()

if __name__ == "__main__":
    main()
