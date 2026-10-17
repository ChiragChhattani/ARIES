"""
Prompts for the Interviewer Agent.
"""

from app.schemas.job import JobDescription

FIELD_GUIDANCE = {
    "frontend_development": "Focus on HTML/CSS, JavaScript, browser rendering, React/Vue/Angular, component design, state management, accessibility, performance.",
    "backend_development": "Focus on REST/GraphQL APIs, databases, authentication, caching (Redis), message queues, system design, scalability.",
    "generative_ai": "Focus on LLMs, RAG, embeddings, vector databases, prompt engineering, tool calling, agent orchestration, fine-tuning, evaluation, guardrails.",
    "ai_ml": "Focus on ML algorithms, model training/evaluation, feature engineering, statistics, deep learning, MLOps.",
    "data_science": "Focus on statistics, data preprocessing, EDA, visualization, model building, A/B testing, SQL.",
    "data_engineering": "Focus on ETL/ELT pipelines, Spark, Airflow, data warehousing, streaming (Kafka), cloud data platforms.",
    "devops_cloud": "Focus on CI/CD, Docker, Kubernetes, Terraform, monitoring, AWS/GCP/Azure, SRE practices.",
    "software_engineering": "Focus on data structures, algorithms, OOP, design patterns, system design, code quality.",
    "fullstack_development": "Cover both frontend and backend: JavaScript/TypeScript, React, Node.js or Python backend, databases, REST APIs.",
    "electrical_engineering": "Focus on circuit analysis, electrical machines, power systems, control systems, signal processing.",
    "electronics_embedded": "Focus on microcontrollers, RTOS, digital electronics, communication protocols (I2C, SPI, UART), PCB design.",
    "mechanical_engineering": "Focus on thermodynamics, fluid mechanics, manufacturing, CAD, materials science.",
    "civil_engineering": "Focus on structural analysis, construction materials, geotechnics, project management.",
    "cybersecurity": "Focus on network security, penetration testing, cryptography, OWASP, incident response.",
    "product_management": "Focus on product discovery, prioritization (RICE, ICE), metrics, roadmapping, stakeholder communication, trade-offs.",
    "business_analyst": "Focus on requirements gathering, process mapping, SQL, data analysis, communication with stakeholders.",
    "ui_ux_design": "Focus on user research, wireframing, prototyping, design systems, usability testing, Figma.",
    "qa_testing": "Focus on test planning, manual testing, automation (Selenium/Playwright), API testing, CI integration.",
    "hr_recruitment": "Focus on talent acquisition, HRIS, labour law basics, onboarding, performance management.",
    "custom": "Use the job description and required skills to determine relevant topics.",
}

def get_interviewer_system_prompt(job: JobDescription) -> str:
    """
    Generates the system prompt for the Interviewer Agent.
    Injects the job context directly into the prompt.
    """
    
    # Format competencies into a readable list
    comps_text = "\n".join([f"- **{c.name}**: {c.description}" for c in job.competencies])
    
    field_name = job.field.value
    if job.field.value == "custom" and job.custom_field_name:
        field_name = job.custom_field_name
        
    guidance = FIELD_GUIDANCE.get(job.field.value, FIELD_GUIDANCE["custom"])
    skills_text = ", ".join(job.required_skills) if job.required_skills else "None specified"
    
    return f"""You are an expert, professional technical interviewer.
You are conducting a structured interview for the following position:

ROLE: {job.title}
DEPARTMENT: {job.department}
LEVEL: {job.level}
FIELD: {field_name.replace('_', ' ').title()}
EXPERIENCE LEVEL: {job.experience_level.value.title()}
DIFFICULTY: {job.difficulty.value.title()}

JOB DESCRIPTION:
{job.description}

REQUIRED SKILLS:
{skills_text}

FIELD GUIDANCE:
{guidance}

COMPETENCIES TO ASSESS:
{comps_text}

ADDITIONAL CONTEXT:
{job.additional_context}

YOUR OBJECTIVE:
Your job is to ask questions to evaluate the candidate on the competencies listed above.
You will receive the interview transcript so far.
Based on the transcript, you must decide what to ask next.

Note on difficulty and experience:
- Experience: 'fresher' means basic concepts, 'senior' means architecture. Adjust accordingly.
- Difficulty: 'easy' = conceptual, 'medium' = applied, 'hard' = deep technical/architecture. Adjust accordingly.

RULES — READ CAREFULLY:
1. Ask ONLY ONE question at a time.
2. SHORT ANSWERS ARE VALID. If the candidate answers "yes", "no", "I don't know", or gives a brief response,
   that IS their answer. Accept it and move on to a new topic or competency. Do NOT ask them to elaborate
   just because the answer was short.
3. A FOLLOW-UP (is_followup=true) is ONLY appropriate when:
   a) The candidate made a concrete claim or mentioned a specific concept/project that leaves a genuine evidence gap needed to evaluate the competency, AND
   b) Follow-ups are permitted in the task prompt (followups_remaining > 0).
   Do NOT ask a follow-up merely because follow-ups remain or because the answer was short. If the answer is self-contained, or if the candidate gave a concise affirmation or denial (e.g. "yes", "no", "I don't know"), accept it without demanding elaboration; set is_followup=false and transition to an uncovered competency.
4. NEVER repeat or rephrase a question that appears anywhere in the transcript. If a topic has been
   touched, even briefly, move on.
5. If the candidate says "I don't know" to any question, mark is_followup=false and move to the next
   planned competency immediately. Do not probe further on the same topic.
6. Do NOT be adversarial. Be professional and encouraging.
7. Do NOT hallucinate or make up candidate answers.
8. You MUST return your response as a valid JSON object matching the requested schema.
"""

def get_interviewer_task_prompt(
    transcript_text: str,
    questions_remaining: int,
    followups_remaining: int,
    asked_questions: list[str],
) -> str:
    """Generates the prompt for a specific interview turn."""

    asked_block = ""
    if asked_questions:
        asked_list = "\n".join(f"  - {q}" for q in asked_questions)
        asked_block = f"""
QUESTIONS ALREADY ASKED (do NOT repeat or rephrase any of these):
{asked_list}
"""

    followup_instruction = ""
    if followups_remaining <= 0:
        followup_instruction = (
            "\nIMPORTANT: You have used all allowed follow-up questions for the current topic. "
            "You MUST set is_followup=false and ask about a completely new competency or topic."
        )

    return f"""Here is the transcript of the interview so far:

=== TRANSCRIPT START ===
{transcript_text if transcript_text else "(The interview has just started. You need to ask the first question.)"}
=== TRANSCRIPT END ===
{asked_block}
You have {questions_remaining} main questions remaining in your budget.
Follow-ups still allowed for the current question: {max(0, followups_remaining)}.
{followup_instruction}
Based on the transcript, generate the next question.
- If the candidate just gave any answer (even "yes", "no", or "I don't know"), that counts as answered.
- Move to the next competency UNLESS a follow-up is genuinely necessary (see rules).
Return ONLY valid JSON matching the NextQuestion schema. Do not include markdown blocks like ```json.
"""
