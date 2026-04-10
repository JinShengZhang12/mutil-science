import json
from typing import Any, Dict


def build_judge_prompt(question_data: Dict[str, Any], student_answer: str) -> str:
    schema = {
        "score": "1|3|5",
        "matched_points": ["..."],
        "missing_points": ["..."],
        "incorrect_points": ["..."],
        "is_goal_reached": False,
        "brief_comment": "不超过40字",
    }
    return (
        "你是评分智能体，请严格输出JSON，不要额外文字。\n"
        f"题目：{question_data.get('question', '')}\n"
        f"标准答案：{question_data.get('answer_key', '')}\n"
        f"学生回答：{student_answer}\n"
        f"输出结构：{json.dumps(schema, ensure_ascii=False)}"
    )


def build_analyzer_prompt(
    question_data: Dict[str, Any],
    student_answer: str,
    judge_result: Dict[str, Any],
    attempt_count: int,
) -> str:
    schema = {
        "reasoning_stage": "guessing|partial_relation|complete_explanation",
        "stage_description": "...",
        "guidance_type": "concept_hint|comparison_hint|affirmation",
        "guidance_message": "...",
    }
    return (
        "你是分析与引导智能体，请严格输出JSON，不要额外文字。\n"
        f"题目：{question_data.get('question', '')}\n"
        f"学生回答：{student_answer}\n"
        f"评分结果：{json.dumps(judge_result, ensure_ascii=False)}\n"
        f"当前是第{attempt_count}次尝试\n"
        f"输出结构：{json.dumps(schema, ensure_ascii=False)}"
    )
