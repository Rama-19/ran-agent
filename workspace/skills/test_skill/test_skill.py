import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--message", default="default message")
args = parser.parse_args()

print(f"test_skill executed: {args.message}")