import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr
from openai import OpenAI

from knowledge_base import LESSON_KB
from logger import log_all_interactions, save_student_dialog, secure_read_logs
from prompts import build_analyzer_prompt, build_judge_prompt
from state_manager import (
    advance_question,
    build_final_summary,
    build_progress_text,
    compute_total_score,
    create_initial_state,
    get_current_question,
    is_session_finished,
    record_attempt,
)

DEFAULT_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "deepseek-chat")
SYSTEM_ROLE = "你是一个严格遵守JSON输出格式的教学辅助智能体。"


def _get_api_key() -> str:
    return (
        os.getenv("OPENAI_API_KEY")
        or os.getenv("DEEPSEEK_API_KEY")
        or os.getenv("HF_TOKEN")
        or ""
    )


def _get_client() -> Optional[OpenAI]:
    api_key = _get_api_key()
    if not api_key:
        return None
    try:
        return OpenAI(api_key=api_key, base_url=DEFAULT_BASE_URL)
    except Exception:
        return None


def _extract_json(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("empty response")

    try:
        return json.loads(raw)
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        raise ValueError("json not found")
    return json.loads(match.group(0))


def _call_llm_json(prompt: str) -> Dict[str, Any]:
    client = _get_client()
    if client is None:
        raise RuntimeError("LLM client unavailable")

    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_ROLE},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    content = response.choices[0].message.content if response.choices else ""
    return _extract_json(content or "")


def _normalize_judge_result(data: Dict[str, Any]) -> Dict[str, Any]:
    raw_score = data.get("score", 1)
    try:
        raw_score = int(raw_score)
    except (TypeError, ValueError):
        raw_score = 1

    if raw_score not in (1, 3, 5):
        if raw_score >= 4:
            raw_score = 5
        elif raw_score >= 2:
            raw_score = 3
        else:
            raw_score = 1

    return {
        "score": raw_score,
        "matched_points": list(data.get("matched_points", [])),
        "missing_points": list(data.get("missing_points", [])),
        "incorrect_points": list(data.get("incorrect_points", [])),
        "is_goal_reached": bool(data.get("is_goal_reached", False) or raw_score == 5),
        "brief_comment": str(data.get("brief_comment", "请继续完善你的回答。"))[:40],
    }


def _normalize_analyzer_result(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "reasoning_stage": str(data.get("reasoning_stage", "partial_relation")),
        "stage_description": str(data.get("stage_description", "需要进一步梳理左右两边的平衡关系。")),
        "guidance_type": str(data.get("guidance_type", "concept_hint")),
        "guidance_message": str(
            data.get(
                "guidance_message",
                "请先回顾杠杆平衡条件，再分别考虑左边和右边各自提供了多少效果。",
            )
        ),
    }


def _contains_any(text: str, keywords: List[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _fallback_judge(question_data: Dict[str, Any], student_answer: str) -> Dict[str, Any]:
    answer = (student_answer or "").replace(" ", "")
    qid = question_data.get("id")
    matched_points: List[str] = []
    missing_points: List[str] = []
    incorrect_points: List[str] = []
    score = 1

    if qid == 1:
        has_3cm = _contains_any(answer, ["3cm", "3厘米", "3公分", "三厘米"])
        has_right = "右" in answer
        has_reason = _contains_any(answer, ["平衡", "相等", "杠杆", "左边", "右边", "力矩", "乘", "×"])
        if has_3cm:
            matched_points.append("答出了3cm这个关键数值")
        else:
            missing_points.append("没有答出正确位置3cm")
        if has_right:
            matched_points.append("说明了应放在右边")
        else:
            missing_points.append("没有明确说明放在右边")
        if has_reason:
            matched_points.append("尝试用杠杆平衡条件解释理由")
        else:
            missing_points.append("没有根据杠杆平衡条件说明理由")
        score = 5 if (has_3cm and has_right and has_reason) else (3 if has_3cm else 1)

    elif qid == 2:
        has_10kg = _contains_any(answer, ["10kg", "10千克", "10公斤", "十千克", "十公斤"])
        has_15cm = _contains_any(answer, ["15cm", "15厘米", "15公分", "十五厘米"]) or "15" in answer
        has_reason = _contains_any(answer, ["平衡", "相等", "杠杆", "左边", "右边", "力矩", "乘", "×"])
        if has_10kg:
            matched_points.append("答出了10kg这个关键数值")
        else:
            missing_points.append("没有答出正确重量10kg")
        if has_15cm:
            matched_points.append("能对应到右边15cm处这个位置")
        else:
            missing_points.append("没有结合右边15cm处这个已知位置分析")
        if has_reason:
            matched_points.append("尝试用杠杆平衡条件解释理由")
        else:
            missing_points.append("没有根据杠杆平衡条件说明理由")
        score = 5 if (has_10kg and has_reason) else (3 if has_10kg else 1)

    brief_comment_map = {
        5: "答案正确且解释较完整。",
        3: "结果基本正确，但理由还可以更完整。",
        1: "目前答案还不够准确，需要继续思考。",
    }

    return _normalize_judge_result(
        {
            "score": score,
            "matched_points": matched_points,
            "missing_points": missing_points,
            "incorrect_points": incorrect_points,
            "is_goal_reached": score == 5,
            "brief_comment": brief_comment_map[score],
        }
    )


def _fallback_analyzer(
    question_data: Dict[str, Any],
    judge_result: Dict[str, Any],
    attempt_count: int,
) -> Dict[str, Any]:
    qid = question_data.get("id")
    score = int(judge_result.get("score", 1))

    if score == 5:
        return _normalize_analyzer_result(
            {
                "reasoning_stage": "complete_explanation",
                "stage_description": "能够较完整地根据平衡条件解释答案。",
                "guidance_type": "affirmation",
                "guidance_message": "你的思路已经比较完整，可以继续保持这种先比较左右总效果再下结论的方法。",
            }
        )

    if qid == 1:
        message = "请回顾平衡条件：先算左边5×50，再减去右边已有10×10，差值再除以50得到距离。"
    else:
        message = "请先算左边5×50的总效果，再减去右边10×10，剩下部分由15cm处新物体提供。"

    if attempt_count >= 2:
        message = "记住：不能只看一个物体，要比较左边总效果和右边两个物体效果之和是否相等。"

    return _normalize_analyzer_result(
        {
            "reasoning_stage": "partial_relation" if score == 3 else "guessing",
            "stage_description": "已经抓住了部分信息，但还需要把左右两边的总效果关系说完整。",
            "guidance_type": "concept_hint" if score == 1 else "comparison_hint",
            "guidance_message": message,
        }
    )


def judge_agent(question_data: Dict[str, Any], student_answer: str) -> Dict[str, Any]:
    prompt = build_judge_prompt(question_data, student_answer)
    try:
        return _normalize_judge_result(_call_llm_json(prompt))
    except Exception:
        return _fallback_judge(question_data, student_answer)


def analyzer_agent(
    question_data: Dict[str, Any],
    student_answer: str,
    judge_result: Dict[str, Any],
    attempt_count: int,
) -> Dict[str, Any]:
    prompt = build_analyzer_prompt(question_data, student_answer, judge_result, attempt_count)
    try:
        return _normalize_analyzer_result(_call_llm_json(prompt))
    except Exception:
        return _fallback_analyzer(question_data, judge_result, attempt_count)


def scheduler_agent(state: Dict[str, Any], question_data: Dict[str, Any], student_answer: str) -> Tuple[Dict[str, Any], str]:
    question_id = question_data.get("id", state.get("current_question_index", 0) + 1)
    current_attempt = int(state.get("attempt_count", 0)) + 1

    judge_result = judge_agent(question_data, student_answer)
    analysis_result = analyzer_agent(question_data, student_answer, judge_result, current_attempt)
    state = record_attempt(state, question_id, student_answer, judge_result, analysis_result)

    reply_lines = [f"【本次评分】{judge_result['score']}分", f"【点评】{judge_result['brief_comment']}"]

    if judge_result.get("matched_points"):
        reply_lines.append("【已做到】" + "；".join(judge_result["matched_points"][:3]))
    if judge_result.get("missing_points"):
        reply_lines.append("【待补充】" + "；".join(judge_result["missing_points"][:3]))

    if current_attempt >= 2 or judge_result.get("is_goal_reached"):
        reply_lines.append("【本题总结】判断杠杆平衡时要比较左右两侧总效果是否相等。")
        state = advance_question(state)
        if is_session_finished(state, LESSON_KB):
            state["finished"] = True
            reply_lines.append(f"【总分】{compute_total_score(state)}分")
            reply_lines.append(f"【总评】{build_final_summary(state, LESSON_KB)}")
        else:
            next_question = get_current_question(state, LESSON_KB)
            if next_question:
                reply_lines.append(f"【下一题】{next_question.get('question', '')}")
    else:
        reply_lines.append(f"【引导】{analysis_result['guidance_message']}")

    payload = {
        "event": "student_answer",
        "timestamp": datetime.utcnow().isoformat(),
        "student_answer": student_answer,
        "question_id": question_id,
        "judge_result": judge_result,
        "analysis_result": analysis_result,
        "state_snapshot": state,
    }
    student_id = state.get("student_id", "unknown")
    log_all_interactions(student_id, payload)
    save_student_dialog(student_id, payload)
    return state, "\n".join(reply_lines)


def _append_chat(history: List[List[str]], user_text: str, bot_text: str) -> List[List[str]]:
    new_history = list(history or [])
    new_history.append([user_text, bot_text])
    return new_history


def start_session(student_id: str):
    student_id = (student_id or "").strip()
    if not student_id:
        return None, [], "请输入“组号+姓名”后再开始。"

    state = create_initial_state(student_id)
    first_question = get_current_question(state, LESSON_KB)
    welcome = "欢迎进入三智能体协同的学生科学推理能力辅助系统。请认真作答，每题最多两次作答机会。"
    question_text = first_question.get("question", "题目加载失败。") if first_question else "暂无题目。"
    chat_history = [["系统", f"{welcome}\n\n【第1题】{question_text}"]]

    payload = {"event": "start_session", "timestamp": datetime.utcnow().isoformat(), "state_snapshot": state}
    log_all_interactions(student_id, payload)
    save_student_dialog(student_id, payload)
    return state, chat_history, build_progress_text(state, LESSON_KB)


def submit_answer(student_answer: str, chat_history: List[List[str]], state: Optional[Dict[str, Any]]):
    if not state:
        return None, _append_chat(chat_history or [], "系统提示", "请先输入学生ID并点击“开始答题”。"), "未开始答题"

    if is_session_finished(state, LESSON_KB):
        return state, _append_chat(chat_history or [], student_answer or "（空）", f"已完成全部题目。\n【总评】{build_final_summary(state, LESSON_KB)}"), "已完成"

    answer = (student_answer or "").strip()
    if not answer:
        return state, _append_chat(chat_history or [], "系统提示", "请输入你的答案后再发送。"), build_progress_text(state, LESSON_KB)

    question_data = get_current_question(state, LESSON_KB)
    if not question_data:
        state["finished"] = True
        return state, _append_chat(chat_history or [], answer, f"题目已结束。\n【总评】{build_final_summary(state, LESSON_KB)}"), "已完成"

    new_state, bot_reply = scheduler_agent(state, question_data, answer)
    return new_state, _append_chat(chat_history or [], answer, bot_reply), build_progress_text(new_state, LESSON_KB)


def clear_student_ui():
    return None, [], "", "已清空，请重新输入学生ID并点击开始答题。"


def load_teacher_logs(password: str):
    result = secure_read_logs(password)
    if isinstance(result, dict):
        if not result.get("success"):
            return result.get("message", "读取失败")
        logs = result.get("logs", [])
        return "\n".join(json.dumps(item, ensure_ascii=False) for item in logs) or "暂无日志。"
    if isinstance(result, list):
        return "\n".join(json.dumps(item, ensure_ascii=False) for item in result) or "暂无日志。"
    return str(result)


with gr.Blocks(title="学生科学推理能力辅助系统") as demo:
    gr.Markdown("## 三智能体协同的学生科学推理能力辅助系统")
    gr.Markdown("教学主题：杠杆平衡与多物体力矩叠加")

    session_state = gr.State(value=None)

    with gr.Tabs():
        with gr.Tab("学生答题区"):
            student_id_input = gr.Textbox(label="学生ID（组号+姓名）", placeholder="例如：3张三")
            start_btn = gr.Button("开始答题", variant="primary")
            chatbot = gr.Chatbot(label="答题对话", height=420)
            answer_input = gr.Textbox(label="你的答案", placeholder="请在此输入你的分析过程")
            with gr.Row():
                send_btn = gr.Button("发送", variant="primary")
                clear_btn = gr.Button("清空")
            status_text = gr.Textbox(label="状态提示", interactive=False)

        with gr.Tab("教师日志区"):
            teacher_password = gr.Textbox(label="教师密码", type="password", placeholder="请输入教师密码")
            load_logs_btn = gr.Button("读取日志")
            logs_box = gr.Textbox(label="日志内容", lines=20, interactive=False)

    start_btn.click(fn=start_session, inputs=[student_id_input], outputs=[session_state, chatbot, status_text])

    send_btn.click(fn=submit_answer, inputs=[answer_input, chatbot, session_state], outputs=[session_state, chatbot, status_text]).then(
        lambda: "", outputs=[answer_input]
    )

    answer_input.submit(
        fn=submit_answer, inputs=[answer_input, chatbot, session_state], outputs=[session_state, chatbot, status_text]
    ).then(lambda: "", outputs=[answer_input])

    clear_btn.click(fn=clear_student_ui, outputs=[session_state, chatbot, answer_input, status_text])
    load_logs_btn.click(fn=load_teacher_logs, inputs=[teacher_password], outputs=[logs_box])


if __name__ == "__main__":
    Path("logs").mkdir(parents=True, exist_ok=True)
    demo.launch()
