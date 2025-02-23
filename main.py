import requests
import random
import time
import os
import pyfiglet
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock, Thread
from queue import Queue

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

clear_screen()
columns, rows = shutil.get_terminal_size()

ascii_text = pyfiglet.figlet_format("Dig Finder", font="standard")

lines = ascii_text.split("\n")

positions = []
x = int(columns / 2 - len(max(lines, key=len)) / 2)
for i in range(len(lines)):
    y = int(rows / 2 - len(lines) / 2 + i)
    positions.append(y)

print("\033[1m\033[32m", end="")
for i in range(len(lines)):
    print(f"\033[{positions[i]};{x}H{lines[i]}")
print("\033[1m\033[35m", end="")
print(f"\033[{positions[-1]+1};{x};{x}Â© @Digjhow69 on discord")
print("\033[0m", end="")

def send_webhook_message(webhook_url, message):
    data = {"content": message}
    requests.post(webhook_url, json=data)

def load_proxies_from_file(filename):
    with open(filename, 'r') as file:
        proxies = [line.strip() for line in file]
    return proxies

def get_group_statuses(group_ids, proxy):
    group_ids_str = ",".join(map(str, group_ids))
    url = f"https://groups.roblox.com/v2/groups?groupIds={group_ids_str}"
    try:
        response = requests.get(url, proxies={"http": proxy, "https": proxy})
        if response.status_code == 200:
            group_data_list = response.json().get('data', [])
            results = {}
            for group_data in group_data_list:
                group_id = group_data.get('id')
                if group_data.get('owner') is None:
                    results[group_id] = 'ownerless'
                else:
                    results[group_id] = 'owned'
            return results
        return {}
    except requests.RequestException:
        return {}

def check_group_public_entry(group_id, proxy):
    url = f"https://groups.roblox.com/v1/groups/{group_id}"
    try:
        response = requests.get(url, proxies={"http": proxy, "https": proxy})
        if response.status_code == 200:
            group_data = response.json()
            return group_data.get('publicEntryAllowed', False)
        return False
    except requests.RequestException:
        return False

def check_group_status(batch_group_ids, webhook_url, proxy, lock, count_queue, max_retries=3):
    statuses = get_group_statuses(batch_group_ids, proxy)
    with lock:
        count_queue.put((time.time(), len(batch_group_ids)))  # Increment scan count by the number of group IDs in the batch

    for group_id, status in statuses.items():
        if status == 'ownerless':
            is_public_entry_allowed = check_group_public_entry(group_id, proxy)
            if is_public_entry_allowed:
                print(f"Group ID: {group_id} is ownerless and has public entry allowed.")
                send_webhook_message(webhook_url, f"Group https://roblox.com/groups/{group_id} is ownerless and has public entry allowed.")
            else:
                print(f"Group ID: {group_id} is ownerless but public entry is not allowed.")
        else:
            time.sleep(0.01)
            print(f"Group ID: {group_id} is owned or locked.")

def stat_updater(count_queue):
    count_cache = {}
    while True:
        while not count_queue.empty():
            ts, count = count_queue.get()
            ts = int(ts)
            count_cache[ts] = count_cache.get(ts, 0) + count

        now = time.time()
        total_count = sum(count for ts, count in list(count_cache.items()) if now - ts <= 60)

        count_cache = {ts: count for ts, count in count_cache.items() if now - ts <= 60}

        print(f"[+] Checks Per Minute: {total_count:,}", end="\r")
        time.sleep(0.10)

if __name__ == "__main__":
    start_id = 14076500
    end_id = 14700000
    webhook_url = input("Enter the webhook URL: ")
    proxy_file = "proxies.txt"
    threads_per_proxy = int(input("Enter the number of threads per proxy: "))

    proxies = load_proxies_from_file(proxy_file)
    lock = Lock()
    count_queue = Queue()  # Queue to track scan counts
    start_time = time.time()

    group_ids = list(range(start_id, end_id + 1))
    batch_size = 100

    # Start the stat updater thread
    stat_thread = Thread(target=stat_updater, args=(count_queue,))
    stat_thread.daemon = True
    stat_thread.start()

    with ThreadPoolExecutor(max_workers=threads_per_proxy * len(proxies)) as executor:
        futures = []
        for i in range(0, len(group_ids), batch_size):
            batch_group_ids = group_ids[i:i + batch_size]
            proxy = proxies[i % len(proxies)]  # Rotate through proxies
            future = executor.submit(check_group_status, batch_group_ids, webhook_url, proxy, lock, count_queue)
            futures.append(future)

        for future in as_completed(futures):
            future.result()
