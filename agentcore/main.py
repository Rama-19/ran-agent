from .models import PLAN_STORE, SESSION
from .skills import load_eligible_skills
from .planner import make_plans
from .executor import execute_plan_structured
from .ui import show_plans, show_skills, run_direct_agent, parse_auto_command


def main():
    eligible = load_eligible_skills()
    print(f"加载到 {len(eligible)} 个合格 Skills")
    for s in eligible:
        print(f"  ✓ {s['name']} @ {s['location']}")

    print("\n可用命令：")
    print("  /skills                查看当前可用 skills")
    print("  /plan 你的任务         生成候选计划")
    print("  /plans                 查看当前内存中的计划")
    print("  /run plan_1            执行指定计划")
    print("  /auto 你的任务         自动生成计划并执行第一个")
    print("  /ask 你的任务          不走 planner，直接让 agent 执行")
    print("  exit / quit            退出")

    while True:
        text = input("\n你：").strip()
        if not text:
            continue

        if text.lower() in ["exit", "quit"]:
            break

        eligible = load_eligible_skills()

        if text == "/skills":
            print(show_skills(eligible))

        elif text == "/plans":
            print(show_plans(list(PLAN_STORE.values())))

        elif text.startswith("/plan "):
            task = text[len("/plan "):].strip()
            plans = make_plans(task, eligible)
            print(show_plans(plans))

        elif text.startswith("/run "):
            plan_id = text[len("/run "):].strip()
            result = execute_plan_structured(plan_id, eligible)
            print(result.message)
            if result.status == "blocked" and result.need_input:
                SESSION.set_pending(result.need_input)
                print(f"BLOCKED: {result.need_input.question}")
                print(show_plans([PLAN_STORE[plan_id]]) if plan_id in PLAN_STORE else "")
            elif result.status in ("done", "failed"):
                SESSION.clear_pending()
            if plan_id in PLAN_STORE:
                print(show_plans([PLAN_STORE[plan_id]]))

        elif text.startswith("/auto "):
            opts, task = parse_auto_command(text)

            if not task:
                print("任务不能为空")
                continue
            print(f"[RUN_OPTIONS] web_mode={opts.web_mode}, deep_think={opts.deep_think},"
                  f"cite={opts.require_citations}, max_search_rounds={opts.max_search_rounds}")

            plans = make_plans(task, eligible, options=opts)
            print(show_plans(plans))
            for p in plans:
                print(f"\n尝试执行 {p.id} ...")
                result = execute_plan_structured(p.id, eligible)
                print(result.message)

                if result.status == "blocked" and result.need_input:
                    SESSION.set_pending(result.need_input)
                    print(f"BLOCKED: {result.need_input.question}")
                    print(show_plans([PLAN_STORE[p.id]]))
                    break

                if result.status == "done":
                    SESSION.clear_pending()
                    print(f"\n已成功完成: {p.id}")
                    print(show_plans([PLAN_STORE[p.id]]))
                    break

                if result.status == "failed":
                    SESSION.clear_pending()
                    print(show_plans([PLAN_STORE[p.id]]))

        elif text.startswith("/reply"):
            reply = text[len("/reply "):].strip()

            if not SESSION.state.pending:
                print("当前没有待补充的任务")
                continue

            pending = SESSION.state.pending
            result = execute_plan_structured(
                pending.plan_id,
                eligible,
                resume_reply=reply
            )
            print(result.message)

            if result.status == "blocked" and result.need_input:
                SESSION.set_pending(result.need_input)
                print(f"BLOCKED: {result.need_input.question}")
            else:
                SESSION.clear_pending()

            if pending.plan_id in PLAN_STORE:
                print(show_plans(PLAN_STORE[pending.plan_id]))

        elif text == "/cancel":
            if not SESSION.state.pending:
                print("当前没有到补充的任务。")
                continue

            pending = SESSION.state.pending
            plan = PLAN_STORE.get(pending.plan_id)
            if plan and plan.status == "blocked":
                plan.status = "failed"
                plan.awaiting_user_input = False
                plan.pending_question = ""

            SESSION.clear_pending()
            print("已取消当前待补充任务")

        elif text.startswith("/ask "):
            task = text[len("/ask "):].strip()
            result = run_direct_agent(task, eligible)
            print(result)

        else:
            if SESSION.state.pending:
                pending = SESSION.state.pending
                print(
                    f"当前有待补充任务: {pending.plan_id} / {pending.step_id} \n"
                    f"问题：{pending.question} \n"
                    f"请使用 /reply 你的补充内容来继续，或 /cancel 取消"
                )
                continue

            plans = make_plans(text, eligible)
            print("已生成候选计划：")
            print(show_plans(plans))
            print("你可以用 /run plan_x 来执行，或者 /auto 直接执行。")


if __name__ == "__main__":
    main()
