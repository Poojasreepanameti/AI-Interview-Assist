import streamlit as st
from pypdf import PdfReader
from coach import analyze_profile, generate_questions, evaluate_answers, final_report

st.title("AI Interview Coach")


def read_pdf(file):
    reader = PdfReader(file)
    text = ""

    for page in reader.pages:
        text += page.extract_text() or ""

    return text


resume_file = st.file_uploader(
    "Upload your resume (PDF)",
    type="pdf"
)

job_description = st.text_area(
    "Paste the job description",
    height=200
)


if resume_file:
    resume_text = read_pdf(resume_file)

    if resume_text.strip() == "":
        st.error(
            "Couldn't read text from this PDF. "
            "It may be a scanned image. Try another file."
        )

    else:
        st.success("Resume read successfully!")

        with st.expander("See extracted resume text"):
            st.text(resume_text)

        if st.button("Analyze my profile"):

            if job_description.strip() == "":
                st.warning("Please paste a job description first.")

            else:
                with st.spinner("Analyzing your profile..."):
                    st.session_state.pop("questions", None)
                    st.session_state.resume_text = resume_text
                    st.session_state.job_description = job_description

                    st.session_state.analysis = analyze_profile(
                        resume_text,
                        job_description
                    )


if "analysis" in st.session_state:

    a = st.session_state.analysis

    st.header(
        f"Profile analysis: {a.get('role', 'Role')}"
    )

    st.metric(
        "Match score",
        f"{a.get('match_score', 0)}%"
    )

    st.write(
        a.get("summary", "")
    )

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Matching skills")

        for skill in a.get("matching_skills", []):
            st.write("-", skill)

    with col2:
        st.subheader("Missing skills")

        for skill in a.get("missing_skills", []):
            st.write("-", skill)

    with st.expander("See raw JSON from the AI"):
        st.json(a)

if "analysis" in st.session_state:
    st.divider()
    st.header("Interview questions")

    num = st.slider("How many questions?", 3, 10, 5)

    if st.button("Generate questions"):
        st.session_state.interview_started = False
        with st.spinner("Writing questions for you..."):
            result = generate_questions(
                st.session_state.analysis,
                st.session_state.resume_text,
                st.session_state.job_description,
                num,
            )

            st.session_state.questions = result.get("questions", [])

if "questions" in st.session_state and st.session_state.questions:
    st.success(f"{len(st.session_state.questions)} questions are ready.")

    if st.button("Start interview"):
        st.session_state.pop("evaluations", None)
        st.session_state.pop("report", None)
        first_q = st.session_state.questions[0]["question"]
        st.session_state.interview_started = True
        st.session_state.current_q = 0
        st.session_state.answers = []
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Hi! Let's begin. Answer as you would in a real interview."
            },
            {
                "role": "assistant",
                "content": f"**Q1.** {first_q}"
            },
        ]

if "questions" in st.session_state and st.session_state.get("interview_started"):
    st.divider()
    st.header("Interview")

    questions = st.session_state.questions
    current = st.session_state.current_q
    total = len(questions)

    st.progress(
        current / total,
        text=f"Answered {current} of {total}"
    )

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if current < total:
        answer = st.chat_input("Type your answer...")

        if answer:
            q = questions[current]

            st.session_state.messages.append({
                "role": "user",
                "content": answer
            })

            st.session_state.answers.append({
                "question": q.get("question"),
                "type": q.get("type"),
                "skill": q.get("skill"),
                "answer": answer,
            })

            st.session_state.current_q += 1

            nxt = st.session_state.current_q

            if nxt < total:
                next_text = f"**Q{nxt + 1}.** {questions[nxt]['question']}"
            else:
                next_text = "That's the end of the interview. Thank you!"

            st.session_state.messages.append({
                "role": "assistant",
                "content": next_text
            })

            st.rerun()

    else:
        st.success("Interview complete! Your answers are saved.")

        if st.button("Evaluate my answers"):
            with st.spinner("Evaluating your answers..."):
                result = evaluate_answers(
                    st.session_state.answers,
                    st.session_state.analysis.get("role", "this job"),
                )

                evaluations = result.get("evaluations", [])

                for e in evaluations:
                    parts = [
                        e.get(k, 0)
                        for k in ["relevance", "depth", "clarity", "examples"]
                    ]
                    e["score"] = round(sum(parts) / len(parts), 1)

                st.session_state.evaluations = evaluations

        if "evaluations" in st.session_state:
            st.header("📝 Answer-by-answer feedback")

            pairs = zip(
                st.session_state.answers,
                st.session_state.evaluations
            )

            for i, (ans, ev) in enumerate(pairs, start=1):
                with st.expander(f"Q{i}: Score {ev['score']}/10"):
                    st.markdown(f"**Question:** {ans['question']}")
                    st.markdown(f"**Your answer:** {ans['answer']}")

                    c1, c2, c3, c4 = st.columns(4)

                    c1.metric("Relevance", ev.get("relevance", 0))
                    c2.metric("Depth", ev.get("depth", 0))
                    c3.metric("Clarity", ev.get("clarity", 0))
                    c4.metric("Examples", ev.get("examples", 0))

                    st.markdown(
                        f"**Feedback:** {ev.get('feedback', '')}"
                    )

                    st.info(
                        f"💡 {ev.get('better_answer_tip', '')}"
                    )

if st.session_state.get("interview_started") and "evaluations" in st.session_state:
    st.divider()
    st.header("🏆 Final scorecard")

    evals = st.session_state.evaluations
    overall = round(sum(e["score"] for e in evals) / len(evals), 1)

    if overall >= 7.5:
        readiness = "✅ Ready for interviews"
    elif overall >= 5:
        readiness = "🟡 Almost ready, a bit more practice"
    else:
        readiness = "🔴 Needs more practice"

    c1, c2 = st.columns(2)
    c1.metric("Interview score", f"{overall}/10")
    c2.metric(
        "Resume match",
        f"{st.session_state.analysis.get('match_score', 0)}%"
    )

    st.subheader(readiness)

    st.markdown("#### Score by rubric area")

    for area in ["relevance", "depth", "clarity", "examples"]:
        avg = sum(e.get(area, 0) for e in evals) / len(evals)
        st.write(f"**{area.title()}**: {avg:.1f}/10")
        st.progress(min(avg / 10, 1.0))

    if st.button("Get my improvement plan"):
        with st.spinner("Preparing your personal feedback..."):
            st.session_state.report = final_report(
                st.session_state.analysis,
                st.session_state.answers,
                evals,
            )

    if "report" in st.session_state:
        r = st.session_state.report

        st.markdown("#### 💪 Strengths")
        for item in r.get("strengths", []):
            st.write("-", item)

        st.markdown("#### 🎯 Areas to improve")
        for item in r.get("improvements", []):
            st.write("-", item)

        st.markdown("#### 📚 Study plan")
        for item in r.get("study_plan", []):
            st.write("-", item)

        st.success(r.get("message", ""))

        lines = [
            "AI INTERVIEW COACH - SCORECARD",
            f"Role: {st.session_state.analysis.get('role', '')}",
            f"Interview score: {overall}/10",
            f"Resume match: {st.session_state.analysis.get('match_score', 0)}%",
            f"Readiness: {readiness}",
            "",
            "STRENGTHS:",
            *[f"- {x}" for x in r.get("strengths", [])],
            "",
            "AREAS TO IMPROVE:",
            *[f"- {x}" for x in r.get("improvements", [])],
            "",
            "STUDY PLAN:",
            *[f"- {x}" for x in r.get("study_plan", [])],
        ]

        st.download_button(
            "📄 Download scorecard",
            "\n".join(lines),
            file_name="interview_scorecard.txt",
        )
            