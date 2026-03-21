# 用markdown格式写笔记
import time
import argparse
from datetime import datetime
import logging

parser = argparse.ArgumentParser()
parser.add_argument("--title", type=str, default="", help="笔记标题")
parser.add_argument("--content", type=str, nargs='+', default=[], help="笔记内容，支持多行，用空格分隔或加引号")
args = parser.parse_args()
# 将列表连接为多行内容
content = '\n'.join(args.content) if args.content else ""

logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="write_note.log",
    filemode="a",
    encoding="utf-8",
    )

def write_note(title, content):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 生成一个md文件，内容是笔记标题和内容
    with open(f"./notes/{title}.md", "w",encoding="utf-8") as f:
        f.write(f"{content}\n")
        f.write(f"---\n")
        f.write(f"created: {now}\n")
        

if __name__ == "__main__":
    write_note(args.title, content)
    logging.info(f"写了一个标题为 {args.title} 的笔记")
    logging.info(f"笔记内容为 {content}")