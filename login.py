import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random
import string
from datetime import datetime
import time

# ---------------------------------------------------------
# 1. إعدادات التصميم والعناوين (UI Configuration)
# ---------------------------------------------------------
st.set_page_config(
    page_title="المعاهد العليا | Higher Institutes System",
    layout="wide",
    page_icon="🏛️",
    initial_sidebar_state="expanded"
)

# --- ثوابت النظام ---
SHEET_NAME = "users_database"
BASE_TUITION = 18000
BOOK_FEES_MAP = {1: 2000, 2: 2500, 3: 3000, 4: 3500}

# --- تعريف هيكل البيانات الكامل (Full Schema) ---
# هذه القوائم تضمن أن الإكسل دائماً منظم ولا يحدث فيه تضارب
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
# 2. المحرك الخلفي (Backend Engine)
# ---------------------------------------------------------

@st.cache_resource
def get_client():
    """الاتصال الآمن بجوجل"""
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
            st.error("⚠️ لم يتم العثور على مفاتيح الربط (Secrets).")
            return None
    except Exception as e:
        st.error(f"حدث خطأ في الاتصال: {e}")
        return None

def init_system_structure():
    """
    🛠️ الدالة المصلحة: تقوم بفحص الشيتات وإصلاح العناوين تلقائياً
    هذه الدالة تحل مشكلة 'duplicates header' نهائياً.
    """
    client = get_client()
    if not client: return False

    try:
        sheet = client.open(SHEET_NAME)
    except:
        st.error(f"لم يتم العثور على ملف {SHEET_NAME} في جوجل درايف!")
        return False

    structure = {
        "Students_Main": HEADERS_STUDENT,
        "Teachers_Main": HEADERS_TEACHER,
        "Subjects_Data": HEADERS_SUBJECTS
    }

    for ws_name, expected_headers in structure.items():
        try:
            try:
                ws = sheet.worksheet(ws_name)
            except:
                # إنشاء الشيت لو مش موجود
                ws = sheet.add_worksheet(ws_name, 1000, len(expected_headers))
            
            # قراءة الصف الأول
            current_headers = ws.row_values(1)
            
            # إذا كان فارغاً أو مختلفاً، نقوم بإعادة كتابته
            if not current_headers or current_headers != expected_headers:
                # تكبير الشيت ليتسع للأعمدة
                ws.resize(cols=len(expected_headers))
                # تحديث الصف الأول دفعة واحدة
                cell_list = ws.range(1, 1, 1, len(expected_headers))
                for i, cell in enumerate(cell_list):
                    cell.value = expected_headers[i]
                ws.update_cells(cell_list)
        except Exception as e:
            st.warning(f"جاري تهيئة {ws_name}... ({e})")
            
    return True

def get_data(ws_name):
    client = get_client()
    if not client: return pd.DataFrame()
    try:
        sheet = client.open(SHEET_NAME)
        ws = sheet.worksheet(ws_name)
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

# ---------------------------------------------------------
# 3. المنطق (Logic)
# ---------------------------------------------------------

def generate_secure_code(role):
    """توليد كود مميز"""
    digits = ''.join(random.choices(string.digits, k=7))
    if role == "Teacher":
        # حرفين كابتل + 8 أرقام
        prefix = ''.join(random.choices(string.ascii_uppercase, k=2))
        return f"{prefix}{digits}9"
    else:
        # حرف كابتل + 7 أرقام
        prefix = random.choice(string.ascii_uppercase)
        return f"{prefix}{digits}"

def calculate_fees_total(current_year):
    fees = BASE_TUITION
    try: y = int(current_year)
    except: y = 1
    # زيادة 10% تراكمية
    for _ in range(1, y):
        fees += fees * 0.10
    return int(fees)

def register_logic(role, form_data):
    client = get_client()
    sheet = client.open(SHEET_NAME)
    
    if role == "Teacher":
        ws_name = "Teachers_Main"
        headers = HEADERS_TEACHER
    else:
        ws_name = "Students_Main"
        headers = HEADERS_STUDENT

    ws = sheet.worksheet(ws_name)
    
    # التأكد من عدم تكرار الكود
    try: existing = ws.col_values(1)
    except: existing = []
    
    while True:
        new_code = generate_secure_code(role)
        if new_code not in existing:
            break
            
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    
    # إضافة البيانات المولدة للنظام
    form_data["Code"] = new_code
    form_data["Password"] = password
    form_data["Join_Date"] = str(datetime.now())
    
    if role == "Student":
        form_data["Year"] = 1
        form_data["Paid_Tuition"] = 0
        form_data["Paid_Books"] = 0

    # ترتيب البيانات حسب الهيدر بدقة
    row_to_add = []
    for h in headers:
        row_to_add.append(form_data.get(h, ""))
        
    ws.append_row(row_to_add)
    
    # إنشاء الملف الشخصي
    try:
        try: sheet.worksheet(new_code)
        except:
            ws_p = sheet.add_worksheet(new_code, 100, 10)
            ws_p.append_row(["البيان", "القيمة/الحالة", "التاريخ", "Link"])
            ws_p.append_row(["تنبيه", "هذا السجل رسمي ولا يعدل إلا بمعرفة الإدارة", str(datetime.now()), ""])
    except: pass
    
    return new_code, password

# ---------------------------------------------------------
# 4. الواجهات (Portals)
# ---------------------------------------------------------

def admin_portal():
    st.markdown("""
    <div style='text-align: center; color: #1f77b4;'>
        <h1>🏛️ المعاهد العليا | بوابة الإدارة</h1>
        <p>System Admin Dashboard V5</p>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs(["🆕 تسجيل طلاب", "👨‍🏫 تسجيل معلمين", "💰 الخزينة", "📚 المواد الدراسية"])
    
    # --- تسجيل طلاب ---
    with tab1:
        st.subheader("ملف طالب جديد")
        with st.form("student_full_reg"):
            st.markdown("##### 1. البيانات الشخصية")
            c1, c2, c3 = st.columns(3)
            name = c1.text_input("الاسم رباعي (كما في البطاقة)")
            nid = c2.text_input("الرقم القومي (14 رقم)")
            nid_src = c3.text_input("جهة الإصدار")
            
            c4, c5, c6 = st.columns(3)
            dob = c4.date_input("تاريخ الميلاد", min_value=datetime(1990,1,1))
            nat = c5.text_input("الجنسية", "مصر")
            rel = c6.selectbox("الديانة", ["مسلم", "مسيحي", "أخرى"])
            
            st.markdown("##### 2. بيانات التواصل والسكن")
            c7, c8, c9 = st.columns(3)
            gov = c7.text_input("المحافظة")
            addr = c8.text_input("العنوان بالتفصيل")
            phone = c9.text_input("رقم هاتف الطالب")
            parent_phone = st.text_input("رقم ولي الأمر")
            
            st.markdown("##### 3. المؤهل الدراسي")
            cc1, cc2, cc3 = st.columns(3)
            cert = cc1.text_input("نوع الشهادة (ثانوية/دبلوم/معادلة)")
            cert_year = cc2.text_input("سنة الشهادة")
            seat = cc3.text_input("رقم الجلوس")
            
            cc4, cc5 = st.columns(2)
            score = cc4.number_input("المجموع الكلي", min_value=0.0)
            major = cc5.selectbox("التخصص المراد", ["نظم معلومات إدارية", "محاسبة", "إدارة أعمال", "سياحة وفنادق"])
            
            notes = st.text_area("ملاحظات إضافية")
            
            submitted = st.form_submit_button("حفظ وتسجيل الطالب")
            
            if submitted and name and nid:
                with st.spinner("جاري معالجة البيانات وإنشاء الملف..."):
                    data = {
                        "Name": name, "National_ID": nid, "NID_Source": nid_src, "DOB": str(dob),
                        "Nationality": nat, "Religion": rel, "Governorate": gov, "Address": addr,
                        "Phone": phone, "Guardian_Phone": parent_phone, "Certificate": cert,
                        "Cert_Year": cert_year, "Seat_Num": seat, "Total_Score": score,
                        "Major": major, "Notes": notes
                    }
                    code, pwd = register_logic("Student", data)
                st.success("✅ تم تسجيل الطالب بنجاح")
                st.info(f"كود الطالب: {code}")
                st.code(pwd, language="text") # عرض الباسوورد للنسخ

    # --- تسجيل معلمين ---
    with tab2:
        st.subheader("ملف عضو هيئة تدريس")
        with st.form("teacher_full_reg"):
            t1, t2 = st.columns(2)
            tn = t1.text_input("الاسم رباعي")
            tnid = t2.text_input("الرقم القومي")
            
            t3, t4, t5 = st.columns(3)
            tdob = t3.date_input("تاريخ الميلاد", min_value=datetime(1960,1,1))
            tphone = t4.text_input("رقم الهاتف")
            temail = t5.text_input("البريد الإلكتروني")
            
            tspec = st.text_input("التخصص الأكاديمي")
            taddr = st.text_input("العنوان")
            
            tsub = st.form_submit_button("تسجيل المعلم")
            if tsub and tn:
                with st.spinner("جاري الحفظ..."):
                    data = {
                        "Name": tn, "National_ID": tnid, "DOB": str(tdob),
                        "Phone": tphone, "Email": temail, "Specialization": tspec,
                        "Address": taddr, "Nationality": "مصر"
                    }
                    code, pwd = register_logic("Teacher", data)
                st.success("✅ تم إنشاء الحساب")
                st.warning(f"الكود: {code} | الباسوورد: {pwd}")

    # --- الخزينة ---
    with tab3:
        st.subheader("نظام المدفوعات الذكي")
        search_q = st.text_input("بحث عن طالب (كود)", key="search_pay")
        
        if st.button("بحث") or 'pay_st' in st.session_state:
            if search_q:
                df = get_data("Students_Main")
                if not df.empty:
                    df['Code'] = df['Code'].astype(str).str.strip()
                    res = df[df['Code'] == str(search_q).strip()]
                    if not res.empty:
                        st.session_state['pay_st'] = res.iloc[0].to_dict()
                    else:
                        st.error("طالب غير موجود")
        
        if 'pay_st' in st.session_state:
            stu = st.session_state['pay_st']
            st.markdown(f"### الطالب: {stu['Name']}")
            
            try: yr = int(stu['Year'])
            except: yr = 1
            
            # حسابات دقيقة
            tuition_full = calculate_fees_total(yr)
            books_full = BOOK_FEES_MAP.get(yr, 2000)
            
            def safe_money(val):
                return int(str(val).replace(',','')) if str(val).replace(',','').isdigit() else 0
            
            paid_t = safe_money(stu['Paid_Tuition'])
            paid_b = safe_money(stu['Paid_Books'])
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.info("مصاريف دراسية")
                st.metric("المستحق", f"{tuition_full:,}")
                st.metric("المتبقي", f"{tuition_full - paid_t:,}", delta_color="inverse")
            with col_b:
                st.info("مصاريف الكتب")
                st.metric("المستحق", f"{books_full:,}")
                st.metric("المتبقي", f"{books_full - paid_b:,}", delta_color="inverse")
                
            st.divider()
            
            pay_opt = st.selectbox("بند السداد", ["مصاريف دراسية", "كتب دراسية"])
            method = st.radio("طريقة الدفع", ["كاش", "فيزا"], horizontal=True)
            
            visa_inf = ""
            if method == "فيزا":
                c_n = st.text_input("رقم الكارت (آخر 4 أرقام للحفظ)", max_chars=16)
                visa_inf = f"Visa-xxxx-{c_n[-4:] if len(c_n)>4 else c_n}"
            
            rem_amount = (tuition_full - paid_t) if pay_opt == "مصاريف دراسية" else (books_full - paid_b)
            amount = st.number_input("المبلغ", min_value=0, max_value=int(rem_amount) if rem_amount > 0 else 0)
            
            if st.button("تأكيد الدفع 💸"):
                if amount > 0:
                    client = get_client()
                    sheet = client.open(SHEET_NAME)
                    ws = sheet.worksheet("Students_Main")
                    cell = ws.find(str(stu['Code']))
                    
                    # العمود 5 للمصاريف، 6 للكتب (حسب الهيدر الجديد)
                    col_idx = 5 if pay_opt == "مصاريف دراسية" else 6
                    current_paid = paid_t if pay_opt == "مصاريف دراسية" else paid_b
                    
                    ws.update_cell(cell.row, col_idx, current_paid + amount)
                    
                    # إيصال
                    note = f"سداد {pay_opt} ({method}) {visa_inf}"
                    try:
                        sheet.worksheet(str(stu['Code'])).append_row([pay_opt, f"{amount} EGP", str(datetime.now()), ""])
                    except: pass
                    
                    st.success("تمت العملية بنجاح!")
                    del st.session_state['pay_st']
                    time.sleep(1)
                    st.rerun()

    # --- المواد ---
    with tab4:
        st.subheader("إسناد المواد (Academic Assigning)")
        
        t_df = get_data("Teachers_Main")
        if not t_df.empty:
            t_list = [f"{r['Name']} | {r['Code']}" for i, r in t_df.iterrows()]
            sel_t = st.selectbox("المعلم", t_list)
            
            c1, c2, c3 = st.columns(3)
            sub = c1.text_input("اسم المادة")
            yl = c2.selectbox("الفرقة", [1, 2, 3, 4])
            tm = c3.selectbox("الترم", ["الأول", "الثاني"])
            
            if st.button("إضافة المادة"):
                tc = sel_t.split(" | ")[1]
                tn = sel_t.split(" | ")[0]
                client = get_client()
                sheet = client.open(SHEET_NAME)
                sheet.worksheet("Subjects_Data").append_row([sub, tc, tn, yl, tm])
                st.success("تم الإسناد")

def teacher_portal():
    u = st.session_state['user']
    st.markdown(f"## 👨‍🏫 مرحباً، د/ {u['Name']}")
    
    # جلب المواد
    df = get_data("Subjects_Data")
    if not df.empty:
        df['Teacher_Code'] = df['Teacher_Code'].astype(str)
        my_subs = df[df['Teacher_Code'] == str(u['Code'])]
        
        if not my_subs.empty:
            st.success(f"لديك {len(my_subs)} مادة مسندة.")
            for i, row in my_subs.iterrows():
                with st.expander(f"📘 {row['Subject_Name']} (فرقة {row['Year_Level']} - {row['Term']})"):
                    st.write("أدوات الكنترول:")
                    c1, c2 = st.columns([3, 1])
                    st_search = c1.text_input("كود الطالب", key=f"s{i}")
                    res = c2.selectbox("التقدير", ["ناجح", "راسب", "ممتاز", "جيد جداً"], key=f"r{i}")
                    
                    if st.button("رصد", key=f"b{i}"):
                        if st_search:
                            client = get_client()
                            try:
                                # كتابة في شيت الطالب
                                sheet = client.open(SHEET_NAME)
                                ws_s = sheet.worksheet(st_search)
                                ws_s.append_row([f"نتيجة: {row['Subject_Name']}", res, str(datetime.now()), ""])
                                st.success(f"تم رصد {res} للطالب")
                            except:
                                st.error("تأكد من كود الطالب")
        else:
            st.warning("لا توجد مواد.")
    
    if st.button("خروج"):
        st.session_state['role'] = None
        st.rerun()

def student_portal():
    u = st.session_state['user']
    st.markdown(f"## 🎓 الطالب/ {u['Name']}")
    st.caption(f"Code: {u['Code']} | Major: {u['Major']}")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("الفرقة", u['Year'])
    
    # Financial Check
    try: y = int(u['Year'])
    except: y = 1
    total = calculate_fees_total(y)
    paid = int(str(u['Paid_Tuition']).replace(',','')) if str(u['Paid_Tuition']).replace(',','').isdigit() else 0
    
    col2.metric("المصاريف", f"{paid:,} / {total:,}")
    col3.metric("المتبقي", f"{total - paid:,}", delta_color="inverse")
    
    st.divider()
    st.subheader("الملف الأكاديمي والنتائج")
    
    try:
        client = get_client()
        sheet = client.open(SHEET_NAME)
        ws = sheet.worksheet(str(u['Code']))
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        # تنسيق الجدول بشكل جبار
        st.dataframe(
            df,
            column_config={
                "Link": st.column_config.LinkColumn("رابط خارجي", display_text="🔗 فتح"),
                "التاريخ": st.column_config.DatetimeColumn("التاريخ", format="D MMM YYYY")
            },
            use_container_width=True,
            hide_index=True
        )
    except:
        st.info("جاري تحديث الملف...")

    if st.button("خروج"):
        st.session_state['role'] = None
        st.rerun()

# ---------------------------------------------------------
# 5. نقطة البداية (Main)
# ---------------------------------------------------------

def main():
    # 1. الإصلاح الذاتي للهيكل عند البدء
    init_system_structure()
    
    if 'role' not in st.session_state: st.session_state['role'] = None
    
    if st.session_state['role']:
        if st.session_state['role'] == "Admin": admin_portal()
        elif st.session_state['role'] == "Teacher": teacher_portal()
        elif st.session_state['role'] == "Student": student_portal()
    else:
        # صفحة الدخول
        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown("# 🏛️")
            st.markdown("### المعاهد العليا")
            st.caption("نظام الإدارة الإلكتروني الموحد V5")
        
        with c2:
            tab_s, tab_t, tab_a = st.tabs(["الطلاب", "المعلمين", "الإدارة"])
            
            with tab_s:
                with st.form("ls"):
                    c = st.text_input("كود الطالب")
                    p = st.text_input("كلمة المرور", type="password")
                    if st.form_submit_button("دخول"):
                        df = get_data("Students_Main")
                        if not df.empty:
                            df['Code'] = df['Code'].astype(str).str.strip()
                            df['Password'] = df['Password'].astype(str).str.strip()
                            u = df[(df['Code'] == str(c).strip()) & (df['Password'] == str(p).strip())]
                            if not u.empty:
                                st.session_state['role'] = "Student"
                                st.session_state['user'] = u.iloc[0].to_dict()
                                st.rerun()
                            else: st.error("بيانات خطأ")
                        else: st.error("لا يوجد طلاب")

            with tab_t:
                with st.form("lt"):
                    c = st.text_input("كود المعلم")
                    p = st.text_input("كلمة المرور", type="password")
                    if st.form_submit_button("دخول"):
                        df = get_data("Teachers_Main")
                        if not df.empty:
                            df['Code'] = df['Code'].astype(str).str.strip()
                            df['Password'] = df['Password'].astype(str).str.strip()
                            u = df[(df['Code'] == str(c).strip()) & (df['Password'] == str(p).strip())]
                            if not u.empty:
                                st.session_state['role'] = "Teacher"
                                st.session_state['user'] = u.iloc[0].to_dict()
                                st.rerun()
                            else: st.error("بيانات خطأ")
            
            with tab_a:
                with st.form("la"):
                    u = st.text_input("المستخدم")
                    p = st.text_input("كلمة المرور", type="password")
                    if st.form_submit_button("دخول"):
                        if u == "admin" and p == "admin123":
                            st.session_state['role'] = "Admin"
                            st.rerun()
                        else: st.error("خطأ")

if __name__ == '__main__':
    main()
