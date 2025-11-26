import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random
import string
from datetime import datetime
import time

# ---------------------------------------------------------
# 1. إعدادات النظام والتصميم الذهبي (Golden UI)
# ---------------------------------------------------------
st.set_page_config(
    page_title="المعاهد العليا | Golden System",
    layout="wide",
    page_icon="🎓",
    initial_sidebar_state="expanded"
)

# تخصيص CSS للغة العربية والتصميم الاحترافي
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Tajawal', sans-serif;
        direction: rtl;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        border-right: 5px solid #ffbd45; /* الذهبي */
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: bold;
    }
    div[data-testid="stExpander"] details summary p {
        font-weight: bold;
        color: #1f77b4;
    }
    h1, h2, h3 {
        color: #2c3e50;
    }
</style>
""", unsafe_allow_html=True)

# --- ثوابت النظام ---
SHEET_NAME = "users_database"
BASE_TUITION = 18000
BOOK_FEES_MAP = {1: 2000, 2: 2500, 3: 3000, 4: 3500}

# --- هيكل البيانات الكامل (The Full Schema) ---
# العناوين دي هي اللي هتتكتب في الإكسل تلقائياً
HEADERS_STUDENT = [
    "Code", "Name", "Password", "Year", "Paid_Tuition", "Paid_Books", 
    "National_ID", "NID_Source", "Phone", "Guardian_Phone", 
    "Address", "Governorate", "Nationality", "Religion", "DOB", 
    "Certificate", "Cert_Year", "Seat_Num", "Total_Score", "Major", 
    "Join_Date", "Notes"
]

HEADERS_TEACHER = [
    "Code", "Name", "Password", "National_ID", "NID_Source", 
    "Phone", "Email", "Address", "Governorate", "Nationality", 
    "Religion", "DOB", "Specialization", "Join_Date"
]

HEADERS_SUBJECTS = ["Subject_Name", "Teacher_Code", "Teacher_Name", "Year_Level", "Term"]

# ---------------------------------------------------------
# 2. المحرك الخلفي (The Engine)
# ---------------------------------------------------------

@st.cache_resource
def get_client():
    """الاتصال بجوجل مرة واحدة فقط (كاش) لسرعة الأداء"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            return client
        else:
            st.error("⚠️ لم يتم العثور على أسرار الاتصال (Secrets).")
            return None
    except Exception as e:
        st.error(f"خطأ اتصال: {e}")
        return None

def auto_fix_schema():
    """
    🛠️ المصلح الذكي (Self-Healing):
    يفحص الملف عند البدء، ويصلح أي عناوين مكررة أو ناقصة تلقائياً.
    """
    client = get_client()
    if not client: return False
    
    try:
        sheet = client.open(SHEET_NAME)
    except:
        st.error(f"الملف {SHEET_NAME} غير موجود!")
        return False

    schema_map = {
        "Students_Main": HEADERS_STUDENT,
        "Teachers_Main": HEADERS_TEACHER,
        "Subjects_Data": HEADERS_SUBJECTS
    }

    for ws_name, expected in schema_map.items():
        try:
            try: ws = sheet.worksheet(ws_name)
            except: ws = sheet.add_worksheet(ws_name, 1000, len(expected))
            
            # فحص الصف الأول
            current = ws.row_values(1)
            
            # إذا كان مختلفاً عن المتوقع، نقوم بإعادة الكتابة
            if current != expected:
                ws.resize(cols=len(expected))
                cell_list = ws.range(1, 1, 1, len(expected))
                for i, cell in enumerate(cell_list):
                    cell.value = expected[i]
                ws.update_cells(cell_list)
        except Exception as e:
            st.warning(f"جاري تهيئة {ws_name}... {e}")
            
    return True

def get_df(ws_name):
    """جلب البيانات كـ DataFrame"""
    client = get_client()
    if not client: return pd.DataFrame()
    try:
        sheet = client.open(SHEET_NAME)
        ws = sheet.worksheet(ws_name)
        return pd.DataFrame(ws.get_all_records())
    except:
        return pd.DataFrame()

# ---------------------------------------------------------
# 3. المنطق (Business Logic)
# ---------------------------------------------------------

def gen_code(role):
    # كود مميز لا يتكرر بسهولة
    nums = ''.join(random.choices(string.digits, k=7))
    if role == "Teacher":
        # يبدأ بحرفين
        prefix = ''.join(random.choices(string.ascii_uppercase, k=2))
        return f"{prefix}{nums}"
    else:
        # يبدأ بحرف
        prefix = random.choice(string.ascii_uppercase)
        return f"{prefix}{nums}"

def calc_fees(year):
    fees = BASE_TUITION
    try: y = int(year)
    except: y = 1
    for _ in range(1, y):
        fees += fees * 0.10 # زيادة 10%
    return int(fees)

def register_user(role, data):
    client = get_client()
    sheet = client.open(SHEET_NAME)
    
    if role == "Teacher":
        ws_name = "Teachers_Main"
        headers = HEADERS_TEACHER
    else:
        ws_name = "Students_Main"
        headers = HEADERS_STUDENT
        
    ws = sheet.worksheet(ws_name)
    
    # التحقق من التكرار
    try: existing = ws.col_values(1)
    except: existing = []
    
    while True:
        code = gen_code(role)
        if code not in existing: break
            
    pwd = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    
    # إضافة البيانات المولدة
    data['Code'] = code
    data['Password'] = pwd
    data['Join_Date'] = str(datetime.now())
    if role == "Student":
        data['Year'] = 1
        data['Paid_Tuition'] = 0
        data['Paid_Books'] = 0
        
    # ترتيب البيانات حسب الهيدر
    row = [data.get(h, "") for h in headers]
    ws.append_row(row)
    
    # إنشاء الشيت الخاص
    try:
        try: sheet.worksheet(code)
        except:
            ws_p = sheet.add_worksheet(code, 100, 10)
            ws_p.append_row(["البيان", "القيمة/الحالة", "التاريخ", "Link"])
            ws_p.append_row(["تنبيه", "هذا السجل رسمي", str(datetime.now()), ""])
    except: pass
    
    return code, pwd

# ---------------------------------------------------------
# 4. بوابات النظام (Portals)
# ---------------------------------------------------------

def admin_dashboard():
    st.markdown("## 🛠️ غرفة التحكم المركزية (Admin Dashboard)")
    st.markdown("---")
    
    # إحصائيات سريعة
    df_s = get_df("Students_Main")
    df_t = get_df("Teachers_Main")
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("إجمالي الطلاب", len(df_s))
    m2.metric("إجمالي المعلمين", len(df_t))
    m3.metric("تاريخ اليوم", str(datetime.now().date()))
    m4.metric("حالة النظام", "نشط ✅")
    
    st.markdown("---")
    
    tab_reg_s, tab_reg_t, tab_fin, tab_acd = st.tabs([
        "👤 تسجيل طلاب", "👨‍🏫 تسجيل معلمين", "💰 الخزينة", "📚 الشؤون الأكاديمية"
    ])
    
    # --- 1. تسجيل الطلاب ---
    with tab_reg_s:
        st.subheader("إضافة طالب جديد للقاعدة")
        with st.form("new_student_v10"):
            c1, c2 = st.columns(2)
            name = c1.text_input("الاسم رباعي (كما في الشهادة)")
            nid = c2.text_input("الرقم القومي (14 رقم)", max_chars=14)
            
            c3, c4, c5 = st.columns(3)
            nid_src = c3.text_input("جهة الإصدار")
            dob = c4.date_input("تاريخ الميلاد", min_value=datetime(1990,1,1))
            phone = c5.text_input("رقم الهاتف")
            
            c6, c7 = st.columns(2)
            gov = c6.text_input("المحافظة")
            addr = c7.text_input("العنوان بالتفصيل")
            
            st.markdown("---")
            st.caption("بيانات المؤهل السابق")
            cc1, cc2, cc3 = st.columns(3)
            cert = cc1.selectbox("نوع الشهادة", ["ثانوية عامة", "ثانوية أزهرية", "دبلوم فني", "معادلة"])
            seat = cc2.text_input("رقم الجلوس")
            score = cc3.number_input("المجموع", min_value=0.0)
            
            cc4, cc5 = st.columns(2)
            major = cc4.selectbox("التخصص المرشح له", ["نظم معلومات إدارية", "محاسبة", "إدارة أعمال"])
            cert_year = cc5.text_input("سنة الحصول على الشهادة")
            
            submit_s = st.form_submit_button("حفظ الطالب")
            if submit_s and name and nid:
                with st.spinner("جاري إنشاء الملف الرقمي..."):
                    d = {
                        "Name": name, "National_ID": nid, "NID_Source": nid_src, "Phone": phone,
                        "DOB": str(dob), "Governorate": gov, "Address": addr, "Certificate": cert,
                        "Seat_Num": seat, "Total_Score": score, "Major": major, "Cert_Year": cert_year,
                        "Nationality": "مصر", "Religion": "غير محدد", "Guardian_Phone": ""
                    }
                    c, p = register_user("Student", d)
                st.success("✅ تم التسجيل بنجاح")
                st.info(f"الكود: {c} | الباسوورد: {p}")

    # --- 2. تسجيل المعلمين ---
    with tab_reg_t:
        st.subheader("إضافة عضو هيئة تدريس")
        with st.form("new_teacher_v10"):
            t1, t2 = st.columns(2)
            tn = t1.text_input("الاسم كامل")
            tnid = t2.text_input("الرقم القومي")
            
            t3, t4 = st.columns(2)
            tphone = t3.text_input("رقم الموبايل")
            temail = t4.text_input("البريد الإلكتروني")
            
            tspec = st.text_input("التخصص الأكاديمي")
            taddr = st.text_input("العنوان")
            
            sub_t = st.form_submit_button("حفظ المعلم")
            if sub_t and tn:
                with st.spinner("جاري الحفظ..."):
                    d = {"Name": tn, "National_ID": tnid, "Phone": tphone, "Email": temail, "Specialization": tspec, "Address": taddr}
                    c, p = register_user("Teacher", d)
                st.success("تم الإنشاء بنجاح 🚀")
                st.warning(f"الكود: {c} | الباسوورد: {p}")

    # --- 3. الخزينة ---
    with tab_fin:
        st.subheader("نظام التحصيل المالي الذكي")
        search = st.text_input("بحث بكود الطالب", key="fin_search")
        if st.button("بحث") or 'fin_user' in st.session_state:
            if search:
                if not df_s.empty:
                    df_s['Code'] = df_s['Code'].astype(str).str.strip()
                    res = df_s[df_s['Code'] == str(search).strip()]
                    if not res.empty:
                        st.session_state['fin_user'] = res.iloc[0].to_dict()
                    else: st.error("غير موجود")

        if 'fin_user' in st.session_state:
            u = st.session_state['fin_user']
            st.markdown(f"**الطالب:** {u['Name']} | **الفرقة:** {u['Year']}")
            
            try: yr = int(u['Year'])
            except: yr = 1
            
            t_total = calc_fees(yr)
            b_total = BOOK_FEES_MAP.get(yr, 2000)
            
            def safe_num(v): return int(str(v).replace(',','')) if str(v).replace(',','').isdigit() else 0
            paid_t = safe_num(u['Paid_Tuition'])
            paid_b = safe_num(u['Paid_Books'])
            
            fc1, fc2 = st.columns(2)
            with fc1:
                st.info("المصاريف الدراسية")
                st.metric("متبقي", f"{t_total - paid_t:,}", delta_color="inverse")
            with fc2:
                st.info("الكتب الدراسية")
                st.metric("متبقي", f"{b_total - paid_b:,}", delta_color="inverse")
                
            pay_for = st.selectbox("السداد لصالح", ["المصاريف", "الكتب"])
            pay_via = st.radio("طريقة الدفع", ["كاش", "فيزا"], horizontal=True)
            
            note_extra = ""
            if pay_via == "فيزا":
                vn = st.text_input("رقم الفيزا", type="password")
                if vn: note_extra = f"Visa..{vn[-4:]}"
                
            rem = (t_total - paid_t) if pay_for == "المصاريف" else (b_total - paid_b)
            amt = st.number_input("المبلغ", 0, int(rem) if rem > 0 else 0)
            
            if st.button("إتمام عملية الدفع"):
                if amt > 0:
                    client = get_client()
                    sheet = client.open(SHEET_NAME)
                    ws = sheet.worksheet("Students_Main")
                    cell = ws.find(str(u['Code']))
                    
                    # تحديث الرصيد (العمود 5 مصاريف، 6 كتب)
                    col = 5 if pay_for == "المصاريف" else 6
                    current = paid_t if pay_for == "المصاريف" else paid_b
                    ws.update_cell(cell.row, col, current + amt)
                    
                    # إيصال
                    try: sheet.worksheet(u['Code']).append_row([pay_for, f"{amt} EGP", str(datetime.now()), note_extra])
                    except: pass
                    
                    st.success("تم الدفع بنجاح!")
                    del st.session_state['fin_user']
                    time.sleep(1)
                    st.rerun()

    # --- 4. المواد ---
    with tab_acd:
        st.subheader("توزيع الخطة الدراسية")
        if not df_t.empty:
            t_opts = [f"{r['Name']} ({r['Code']})" for i,r in df_t.iterrows()]
            sel_t = st.selectbox("المعلم", t_opts)
            c1, c2, c3 = st.columns(3)
            sub_n = c1.text_input("اسم المادة")
            y_l = c2.selectbox("الفرقة", [1, 2, 3, 4])
            term = c3.selectbox("الترم", ["الأول", "الثاني"])
            
            if st.button("إضافة المادة للجدول"):
                client = get_client()
                sheet = client.open(SHEET_NAME)
                tc = sel_t.split(" (")[1][:-1]
                tn = sel_t.split(" (")[0]
                sheet.worksheet("Subjects_Data").append_row([sub_n, tc, tn, y_l, term])
                st.success("تم الإسناد")

def teacher_portal():
    u = st.session_state['user']
    st.markdown(f"## 👨‍🏫 بوابة المعلم: د/ {u['Name']}")
    
    df = get_df("Subjects_Data")
    if not df.empty:
        df['Teacher_Code'] = df['Teacher_Code'].astype(str)
        my_subs = df[df['Teacher_Code'] == str(u['Code'])]
        
        if not my_subs.empty:
            for i, r in my_subs.iterrows():
                with st.expander(f"📘 {r['Subject_Name']} (فرقة {r['Year_Level']})"):
                    col1, col2 = st.columns([3, 1])
                    s_code = col1.text_input("كود الطالب", key=f"src{i}")
                    res = col2.selectbox("التقدير", ["ناجح", "راسب", "امتياز", "جيد جداً"], key=f"res{i}")
                    if st.button("رصد", key=f"btn{i}"):
                        client = get_client()
                        try:
                            sheet = client.open(SHEET_NAME)
                            ws = sheet.worksheet(s_code)
                            ws.append_row([f"نتيجة {r['Subject_Name']}", res, str(datetime.now()), ""])
                            st.success("تم الرصد")
                        except:
                            st.error("كود الطالب غير صحيح")
        else: st.info("لا توجد مواد.")
    else: st.warning("جدول المواد فارغ.")
    
    if st.button("خروج"):
        st.session_state['role'] = None
        st.rerun()

def student_portal():
    u = st.session_state['user']
    st.markdown(f"## 🎓 بوابة الطالب: {u['Name']}")
    
    try: yr = int(u['Year'])
    except: yr = 1
    
    c1, c2, c3 = st.columns(3)
    c1.metric("الفرقة", yr)
    c2.metric("التخصص", u['Major'])
    c3.metric("تاريخ الانضمام", u['Join_Date'][:10])
    
    st.divider()
    st.subheader("📂 السجل الأكاديمي والمالي")
    
    client = get_client()
    try:
        sheet = client.open(SHEET_NAME)
        ws = sheet.worksheet(str(u['Code']))
        data = ws.get_all_records()
        st.dataframe(pd.DataFrame(data), use_container_width=True)
    except:
        st.info("جاري تجهيز الملف...")
        
    if st.button("خروج"):
        st.session_state['role'] = None
        st.rerun()

# ---------------------------------------------------------
# 5. نقطة الدخول الرئيسية (Main)
# ---------------------------------------------------------

def main():
    # 1. الفحص الذاتي وإصلاح الهيدر
    auto_fix_schema()
    
    if 'role' not in st.session_state: st.session_state['role'] = None
    
    if st.session_state['role']:
        if st.session_state['role'] == "Admin": admin_portal()
        elif st.session_state['role'] == "Teacher": teacher_portal()
        elif st.session_state['role'] == "Student": student_portal()
    else:
        # صفحة الدخول الموحدة
        st.markdown("<h1 style='text-align: center; color: #b8860b;'>🏛️ المعاهد العليا</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>نظام الإدارة الإلكتروني الموحد V10</p>", unsafe_allow_html=True)
        st.markdown("---")
        
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.info("🎓 دخول الطلاب")
            with st.form("l_s"):
                u = st.text_input("كود الطالب")
                p = st.text_input("كلمة المرور", type="password")
                if st.form_submit_button("دخول"):
                    df = get_df("Students_Main")
                    if not df.empty:
                        df['Code'] = df['Code'].astype(str).str.strip()
                        df['Password'] = df['Password'].astype(str).str.strip()
                        res = df[(df['Code']==str(u).strip()) & (df['Password']==str(p).strip())]
                        if not res.empty:
                            st.session_state['role'] = "Student"
                            st.session_state['user'] = res.iloc[0].to_dict()
                            st.rerun()
                        else: st.error("بيانات خطأ")
        
        with c2:
            st.warning("👨‍🏫 دخول المعلمين")
            with st.form("l_t"):
                u = st.text_input("كود المعلم")
                p = st.text_input("كلمة المرور", type="password")
                if st.form_submit_button("دخول"):
                    df = get_df("Teachers_Main")
                    if not df.empty:
                        df['Code'] = df['Code'].astype(str).str.strip()
                        df['Password'] = df['Password'].astype(str).str.strip()
                        res = df[(df['Code']==str(u).strip()) & (df['Password']==str(p).strip())]
                        if not res.empty:
                            st.session_state['role'] = "Teacher"
                            st.session_state['user'] = res.iloc[0].to_dict()
                            st.rerun()
                        else: st.error("بيانات خطأ")

        with c3:
            st.error("🔒 الإدارة")
            with st.form("l_a"):
                u = st.text_input("المستخدم")
                p = st.text_input("كلمة المرور", type="password")
                if st.form_submit_button("دخول"):
                    if u == "admin" and p == "admin123":
                        st.session_state['role'] = "Admin"
                        st.rerun()
                    else: st.error("خطأ")

if __name__ == '__main__':
    main()
