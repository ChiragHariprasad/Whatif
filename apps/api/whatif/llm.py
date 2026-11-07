from __future__ import annotations

import os
import re
from typing import Any

import httpx


def render_verdict(result: dict[str, Any], currency_symbol: str = "₹", locale: str = "en-IN") -> dict[str, Any]:
    """Guardrail-safe fallback: only server-owned placeholders can become numbers."""
    plan = result["plan"]; q = plan["profit_delta"]; cash = plan["cash"]
    if q["p50"] > 0 and plan["loss_chance"] < .45:
        template = "Your plan is likely to improve profit by [[profit_p50]], with a likely range of [[profit_p10]] to [[profit_p90]]. The chance it leaves you worse off is [[loss_chance]]."
    else:
        template = "This is not a clear bet yet: the central estimate is [[profit_p50]] and the chance of being worse off is [[loss_chance]]. Start with the smaller test."
    values = {"profit_p10": money(q["p10"], currency_symbol, locale), "profit_p50": money(q["p50"], currency_symbol, locale), "profit_p90": money(q["p90"], currency_symbol, locale), "loss_chance": f"{plan['loss_chance']:.0%}", "lowest_cash": money(cash["min_value"], currency_symbol, locale), "lowest_week": str(cash["min_week"])}
    return {"template": template, "text": substitute(template, values), "values": values, "guardrail": "server-template"}


def substitute(template: str, values: dict[str, str]) -> str:
    names = set(re.findall(r"\[\[([a-z0-9_]+)\]\]", template))
    if not names.issubset(values): raise ValueError("Explanation requested an unknown numeric placeholder")
    if re.search(r"\d", re.sub(r"\[\[[a-z0-9_]+\]\]", "", template)): raise ValueError("Generated prose may not contain literal digits")
    return re.sub(r"\[\[([a-z0-9_]+)\]\]", lambda item: values[item.group(1)], template)


def money(value: float, currency_symbol: str = "₹", locale: str = "en-IN") -> str:
    sign = "−" if value < 0 else "+" if value > 0 else ""
    number = f"{abs(value):,.0f}"
    if locale == "en-IN":
        digits = str(int(round(abs(value))))
        if len(digits) > 3:
            head, tail = digits[:-3], digits[-3:]
            chunks = []
            while head:
                chunks.append(head[-2:]); head = head[:-2]
            number = ",".join(reversed(chunks)) + "," + tail
    return f"{sign}{currency_symbol}{number}"


rupees = money


async def groq_placeholders(context: dict[str, Any]) -> str | None:
    """Optional explanation call. It is never asked to calculate or print literal digits."""
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key: return None
    prompt = "Write one calm planning sentence. Use only these placeholders: [[profit_p10]], [[profit_p50]], [[profit_p90]], [[loss_chance]], [[lowest_cash]], [[lowest_week]]. Never use digits, ordinals, or numbered bullets; write continuous prose only. Context: " + str(context)
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {key}"}, json={"model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"), "messages": [{"role": "user", "content": prompt}], "temperature": .2, "max_tokens": 100})
            response.raise_for_status(); return response.json()["choices"][0]["message"]["content"].strip()
    except Exception: return None
