# 设置计时器在指定时间打印内容
import time
import argparse
from datetime import datetime, timedelta

parser = argparse.ArgumentParser()
parser.add_argument("--time", type=int, default=5, help="等待时间（秒）")
parser.add_argument("--message", type=str, default="时间到了", help="提醒消息")
args = parser.parse_args()

# 设置运行参数

def write_reminder_script(message):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 生成一个txt文件，内容是提醒消息
    with open("reminder.txt", "w",encoding="utf-8") as f:
        f.write(f"{now} 提醒：{message}")

def reminder(time_in_seconds, message):
    time.sleep(time_in_seconds)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{now} 提醒：{message}")

if __name__ == "__main__":
    write_reminder_script(args.message)
    reminder(args.time, args.message)
