"""EduPro – Instructor & Course Quality Dashboard (Streamlit)."""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="EduPro Instructor Analytics", page_icon="🎓", layout="wide")

DATA = Path(__file__).parent / "EduPro_Online_Platform.xlsx"
TIER_ORDER = ["Low", "Mid", "High"]
LOW_CUT, HIGH_CUT = 2.5, 3.8  # ≈ bottom / top quartile of teacher ratings


# ----------------------------------------------------------------- data
@st.cache_data
def load():
    sheets = pd.read_excel(DATA, sheet_name=None)
    teachers, courses, tx = sheets["Teachers"], sheets["Courses"], sheets["Transactions"]
    teachers["Tier"] = pd.cut(
        teachers["TeacherRating"], [-np.inf, LOW_CUT, HIGH_CUT, np.inf],
        labels=TIER_ORDER, right=False,
    )
    merged = (
        tx.merge(courses, on="CourseID", how="left", validate="m:1")
        .merge(teachers, on="TeacherID", how="left", validate="m:1", suffixes=("", "_teacher"))
    )
    return teachers, courses, tx, merged


teachers, courses, tx, df = load()


# ----------------------------------------------------------------- sidebar filters
st.sidebar.header("Filters")
expertise = st.sidebar.multiselect(
    "Instructor expertise", sorted(teachers["Expertise"].unique()),
    default=sorted(teachers["Expertise"].unique()),
)
cats = st.sidebar.multiselect(
    "Course category", sorted(courses["CourseCategory"].unique()),
    default=sorted(courses["CourseCategory"].unique()),
)
levels = st.sidebar.multiselect(
    "Course level", ["Beginner", "Intermediate", "Advanced"],
    default=["Beginner", "Intermediate", "Advanced"],
)
t_rng = st.sidebar.slider("Teacher rating range", 1.0, 5.0, (1.0, 5.0), 0.05)
c_rng = st.sidebar.slider("Course rating range", 1.0, 5.0, (1.0, 5.0), 0.05)

f = df[
    df["Expertise"].isin(expertise)
    & df["CourseCategory"].isin(cats)
    & df["CourseLevel"].isin(levels)
    & df["TeacherRating"].between(*t_rng)
    & df["CourseRating"].between(*c_rng)
]

st.title("🎓 EduPro – Instructor & Course Quality Analytics")
st.caption(
    "Each transaction links one learner enrollment to one course and one teacher. "
    "Filters apply to all tabs; teacher-level figures are computed from the filtered enrollments."
)
if f.empty:
    st.warning("No enrollments match the current filters.")
    st.stop()

# teacher-level table from filtered data
g = f.groupby("TeacherID")
tprof = (
    f.drop_duplicates("TeacherID")[
        ["TeacherID", "TeacherName", "Age", "Gender", "Expertise", "YearsOfExperience", "TeacherRating", "Tier"]
    ].set_index("TeacherID")
    .join(g.size().rename("Enrollments"))
    .join(g["CourseRating"].mean().rename("AvgCourseRating"))
    .join(g["CourseRating"].std().fillna(0).rename("CourseRatingStd"))
    .join(g["CourseID"].nunique().rename("CoursesTaught"))
    .reset_index()
)
# Rating Consistency Index: 1 = every course the teacher is linked to has the same rating;
# 0 = spread equal to the max plausible (std of 2 on a 1–5 scale)
tprof["RCI"] = (1 - tprof["CourseRatingStd"] / 2).clip(0, 1)


def slope_r(x, y):
    if len(x) < 3 or x.nunique() < 2:
        return np.nan, np.nan
    return np.polyfit(x, y, 1)[0], x.corr(y)


slope, r_exp = slope_r(tprof["YearsOfExperience"], tprof["TeacherRating"])
tier_enr = tprof.groupby("Tier", observed=True)["Enrollments"].sum()
tier_cnt = tprof.groupby("Tier", observed=True).size()
if "High" in tier_cnt.index:
    eir = (tier_enr["High"] / tier_enr.sum()) / (tier_cnt["High"] / tier_cnt.sum())
else:
    eir = np.nan

# ----------------------------------------------------------------- KPIs
k = st.columns(5)
k[0].metric("Avg Teacher Rating", f"{tprof['TeacherRating'].mean():.2f}", help="Mean rating across instructors in view")
k[1].metric("Avg Course Rating", f"{f.drop_duplicates('CourseID')['CourseRating'].mean():.2f}",
            help="Mean rating across distinct courses in view")
k[2].metric("Rating Consistency Index", f"{tprof['RCI'].mean():.2f}",
            help="1 − (std of course ratings per teacher ÷ 2), averaged. Higher = more reliable.")
k[3].metric("Experience Impact Score", "n/a" if np.isnan(slope) else f"{slope:+.3f} pts/yr",
            help="Slope of TeacherRating on YearsOfExperience (OLS).")
k[4].metric("Enrollment Influence Ratio", "n/a" if np.isnan(eir) else f"{eir:.2f}×",
            help="Share of enrollments going to High-rated teachers ÷ their share of teachers. >1 = over-indexed.")

tabs = st.tabs(["Overview", "Leaderboard", "Experience vs Rating", "Course Quality",
                "Instructor Impact", "Expertise"])


def trendline(fig, x, y, name="Trend"):
    if len(x) > 2 and x.nunique() > 1:
        m, b = np.polyfit(x, y, 1)
        xs = np.linspace(x.min(), x.max(), 50)
        fig.add_scatter(x=xs, y=m * xs + b, mode="lines", name=name, line=dict(dash="dash", color="gray"))
    return fig


# ----------------------------------------------------------------- Overview
with tabs[0]:
    a, b = st.columns(2)
    fig = px.histogram(tprof, x="TeacherRating", nbins=20, title="Distribution of instructor ratings")
    fig.update_layout(bargap=0.05, yaxis_title="Instructors")
    a.plotly_chart(fig, width="stretch")
    fig = px.box(tprof, x="Expertise", y="TeacherRating", points="all", title="Rating spread by expertise")
    b.plotly_chart(fig, width="stretch")
    a, b = st.columns(2)
    a.plotly_chart(px.histogram(tprof, x="YearsOfExperience", nbins=15, title="Experience distribution"),
                   width="stretch")
    a2 = px.histogram(tprof, x="Age", nbins=15, title="Instructor age distribution")
    b.plotly_chart(a2, width="stretch")
    s = tprof["TeacherRating"]
    st.write(
        f"**{len(tprof)} instructors** · mean {s.mean():.2f} · median {s.median():.2f} · "
        f"SD {s.std():.2f} · skew {s.skew():.2f}"
    )

# ----------------------------------------------------------------- Leaderboard
with tabs[1]:
    n = st.slider("Show top / bottom N", 3, 15, 10)
    min_enr = st.number_input("Minimum enrollments", 0, int(tprof["Enrollments"].max()), 0)
    lb = tprof[tprof["Enrollments"] >= min_enr].sort_values("TeacherRating", ascending=False)
    cols = ["TeacherName", "Expertise", "YearsOfExperience", "TeacherRating", "AvgCourseRating",
            "RCI", "Enrollments", "Tier"]
    fmt = {"TeacherRating": "{:.2f}", "AvgCourseRating": "{:.2f}", "RCI": "{:.2f}"}
    a, b = st.columns(2)
    a.subheader("🏆 Top performers")
    a.dataframe(lb.head(n)[cols].style.format(fmt), hide_index=True, width="stretch")
    b.subheader("⚠️ Needs support")
    b.dataframe(lb.tail(n).sort_values("TeacherRating")[cols].style.format(fmt), hide_index=True,
                width="stretch")
    with st.expander("Full leaderboard"):
        st.dataframe(lb[cols].style.format(fmt), hide_index=True, width="stretch")
        st.download_button("Download CSV", lb[cols].to_csv(index=False), "leaderboard.csv")

# ----------------------------------------------------------------- Experience vs rating
with tabs[2]:
    a, b = st.columns(2)
    fig = px.scatter(tprof, x="YearsOfExperience", y="TeacherRating", color="Expertise",
                     hover_name="TeacherName", title="Experience vs TeacherRating")
    a.plotly_chart(trendline(fig, tprof["YearsOfExperience"], tprof["TeacherRating"]),
                   width="stretch")
    fig = px.scatter(tprof, x="YearsOfExperience", y="AvgCourseRating", color="Expertise",
                     hover_name="TeacherName", title="Experience vs avg CourseRating")
    b.plotly_chart(trendline(fig, tprof["YearsOfExperience"], tprof["AvgCourseRating"]),
                   width="stretch")
    _, r_c = slope_r(tprof["YearsOfExperience"], tprof["AvgCourseRating"])
    _, r_tc = slope_r(tprof["TeacherRating"], tprof["AvgCourseRating"])
    st.write(
        f"Pearson r — Experience↔TeacherRating: **{r_exp:.2f}** · Experience↔CourseRating: **{r_c:.2f}** · "
        f"TeacherRating↔CourseRating: **{r_tc:.2f}**"
    )
    # diminishing returns: rating by experience band
    bands = pd.cut(tprof["YearsOfExperience"], [-1, 3, 6, 9, 12, 100],
                   labels=["0–3", "4–6", "7–9", "10–12", "13+"])
    band_df = tprof.groupby(bands, observed=True).agg(
        Instructors=("TeacherID", "size"), AvgTeacherRating=("TeacherRating", "mean"),
        AvgCourseRating=("AvgCourseRating", "mean")).reset_index().rename(columns={"YearsOfExperience": "Experience band"})
    fig = px.bar(band_df, x="Experience band", y=["AvgTeacherRating", "AvgCourseRating"], barmode="group",
                 title="Ratings by experience band (look for plateaus)")
    st.plotly_chart(fig, width="stretch")

# ----------------------------------------------------------------- Course quality
with tabs[3]:
    cc = f.drop_duplicates("CourseID")
    piv = cc.pivot_table(index="CourseCategory", columns="CourseLevel", values="CourseRating", aggfunc="mean")
    piv = piv.reindex(columns=[c for c in ["Beginner", "Intermediate", "Advanced"] if c in piv.columns])
    fig = px.imshow(piv, text_auto=".2f", aspect="auto", color_continuous_scale="RdYlGn",
                    zmin=1, zmax=5, title="Mean CourseRating: category × level (blank = no course)")
    st.plotly_chart(fig, width="stretch")
    a, b = st.columns(2)
    cat = cc.groupby("CourseCategory")["CourseRating"].agg(["mean", "std", "count"]).reset_index()
    fig = px.bar(cat.sort_values("mean"), x="mean", y="CourseCategory", orientation="h",
                 error_x="std", title="Category mean rating (± SD = consistency)")
    a.plotly_chart(fig, width="stretch")
    gl = f.groupby(["Gender", "CourseLevel"])["CourseRating"].mean().reset_index()
    fig = px.bar(gl, x="CourseLevel", y="CourseRating", color="Gender", barmode="group",
                 category_orders={"CourseLevel": ["Beginner", "Intermediate", "Advanced"]},
                 title="Course rating by instructor gender × level (enrollment-weighted)")
    b.plotly_chart(fig, width="stretch")

# ----------------------------------------------------------------- Instructor impact
with tabs[4]:
    st.caption(f"Tiers: Low < {LOW_CUT} ≤ Mid < {HIGH_CUT} ≤ High (≈ bottom / top quartile of teacher ratings).")
    tier = f.groupby("Tier", observed=True).agg(
        Instructors=("TeacherID", "nunique"), Enrollments=("TransactionID", "count"),
        AvgCourseRating=("CourseRating", "mean")).reset_index()
    tier["Enrollments per instructor"] = tier["Enrollments"] / tier["Instructors"]
    a, b = st.columns(2)
    a.plotly_chart(px.bar(tier, x="Tier", y="AvgCourseRating", range_y=[1, 5], title="Avg course rating by tier"),
                   width="stretch")
    b.plotly_chart(px.bar(tier, x="Tier", y="Enrollments per instructor", title="Enrollments per instructor by tier"),
                   width="stretch")
    fig = px.scatter(tprof, x="TeacherRating", y="Enrollments", color="Expertise", hover_name="TeacherName",
                     title="Teacher rating vs enrollments")
    st.plotly_chart(trendline(fig, tprof["TeacherRating"], tprof["Enrollments"]), width="stretch")
    st.dataframe(tier.style.format({"AvgCourseRating": "{:.2f}", "Enrollments per instructor": "{:.0f}"}),
                 hide_index=True, width="stretch")

# ----------------------------------------------------------------- Expertise
with tabs[5]:
    ex = tprof.groupby("Expertise").agg(
        Instructors=("TeacherID", "size"), AvgTeacherRating=("TeacherRating", "mean"),
        AvgCourseRating=("AvgCourseRating", "mean"), AvgExperience=("YearsOfExperience", "mean"),
        RCI=("RCI", "mean"), Enrollments=("Enrollments", "sum")).reset_index()
    a, b = st.columns(2)
    a.plotly_chart(px.bar(ex.sort_values("AvgTeacherRating"), x="AvgTeacherRating", y="Expertise",
                          orientation="h", color="Instructors", title="Avg teacher rating by expertise"),
                   width="stretch")
    b.plotly_chart(px.scatter(ex, x="AvgTeacherRating", y="AvgCourseRating", size="Enrollments",
                              text="Expertise", title="Expertise: teacher vs course rating"),
                   width="stretch")
    st.subheader("Training-need flags")
    flag = ex[ex["AvgTeacherRating"] < tprof["TeacherRating"].mean() - 0.25].sort_values("AvgTeacherRating")
    st.dataframe(flag.style.format({c: "{:.2f}" for c in ["AvgTeacherRating", "AvgCourseRating", "AvgExperience", "RCI"]}),
                 hide_index=True, width="stretch")
    st.caption("Flagged = average teacher rating more than 0.25 below the platform mean. "
               "Expertise groups with 1–2 instructors are indicative only.")
