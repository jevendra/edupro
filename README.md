# EduPro – Instructor & Course Quality Analytics

Streamlit dashboard evaluating instructor effectiveness, course quality and enrollment impact.

## Run locally
```
pip install -r requirements.txt
streamlit run app.py
```

## Deploy (Streamlit Community Cloud)
1. Push this folder to a GitHub repo (app.py, requirements.txt, EduPro_Online_Platform.xlsx).
2. Go to share.streamlit.io → New app → select repo, branch, `app.py` → Deploy.

## KPI definitions
- **Average Teacher Rating** – mean TeacherRating of instructors in view.
- **Average Course Rating** – mean CourseRating of distinct courses in view.
- **Rating Consistency Index** – 1 − (std of CourseRating across a teacher's enrollments ÷ 2), averaged; higher = more reliable.
- **Experience Impact Score** – OLS slope of TeacherRating on YearsOfExperience (rating points per year).
- **Enrollment Influence Ratio** – share of enrollments going to High-rated teachers ÷ their share of teachers.

Tiers: Low < 2.5 ≤ Mid < 3.8 ≤ High (≈ bottom/top quartile).
Note: courses are linked to teachers only through Transactions, and each course appears with 7–30 teachers.
