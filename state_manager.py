from typing import Any, Dict


def create_initial_state(student_id: str) -> Dict[str, Any]:
    return {
        "student_id": student_id,
        "current_question_index": 0,
        "attempt_count": 0,
        "history": [],
        "finished": False,
    }


def get_current_question(state: Dict[str, Any], lesson_kb: Dict[str, Any]):
    idx = int(state.get("current_question_index", 0))
    questions = lesson_kb.get("questions", [])
    if idx < 0 or idx >= len(questions):
        return None
    return questions[idx]


def record_attempt(
    state: Dict[str, Any],
    question_id: int,
    student_answer: str,
    judge_result: Dict[str, Any],
    analysis_result: Dict[str, Any],
) -> Dict[str, Any]:
    state["attempt_count"] = int(state.get("attempt_count", 0)) + 1
    state.setdefault("history", []).append(
        {
            "question_id": question_id,
            "attempt_count": state["attempt_count"],
            "student_answer": student_answer,
            "judge_result": judge_result,
            "analysis_result": analysis_result,
        }
    )
    return state


def advance_question(state: Dict[str, Any]) -> Dict[str, Any]:
    state["current_question_index"] = int(state.get("current_question_index", 0)) + 1
    state["attempt_count"] = 0
    return state


def is_session_finished(state: Dict[str, Any], lesson_kb: Dict[str, Any]) -> bool:
    total = len(lesson_kb.get("questions", []))
    return bool(state.get("finished")) or int(state.get("current_question_index", 0)) >= total


def compute_total_score(state: Dict[str, Any]) -> int:
    best = {}
    for item in state.get("history", []):
        qid = item.get("question_id")
        score = int(item.get("judge_result", {}).get("score", 0))
        best[qid] = max(best.get(qid, 0), score)
    return sum(best.values())


def build_final_summary(state: Dict[str, Any], lesson_kb: Dict[str, Any]) -> str:
    total_questions = len(lesson_kb.get("questions", []))
    total = compute_total_score(state)
    full = total_questions * 5
    if total >= full * 0.8:
        level = "优秀"
    elif total >= full * 0.6:
        level = "良好"
    else:
        level = "需加强"
    return f"共{total_questions}题，得分{total}/{full}，总体表现：{level}。"


def build_progress_text(state: Dict[str, Any], lesson_kb: Dict[str, Any]) -> str:
    current = int(state.get("current_question_index", 0)) + 1
    total = len(lesson_kb.get("questions", []))
    if is_session_finished(state, lesson_kb):
        return f"已完成全部题目（总分：{compute_total_score(state)}）"
    return f"当前进度：第{current}/{total}题，第{int(state.get('attempt_count', 0)) + 1}次作答"
