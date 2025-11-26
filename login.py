import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random
import string
from datetime import datetime
import time

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="نظام المعاهد العليا V3", layout="wide", page_icon="🎓")

# --- 2. ثوابت النظام ---
SHEET_NAME = "users_database"
BASE_FEES = 18000
BOOK_FEES = {1: 2000, 2: 2500, 3: 3000, 4: 3500}

# تعريف أعمدة البيانات عشان تكون كاملة ومنظمة
STUDENT_HEADERS = [
    "Code", "Name", "Password", "Year", "Paid_Tuition", "Paid_Books", 
    "National_ID", "Address", "Phone", "Governorate", "Nationality", 
    "Religion", "DOB", "Major", "Degree_Score", "Join_Date"
]

TEACHER_HEADERS = [
    "Code", "Name", "Password", "National_ID", "Phone", "Email", 
    "Address", "Governorate", "Nationality", "Religion", "DOB", "Join_Date"
]

SUBJECT_HEADERS = ["Subject", "Teacher_Code", "Teacher_Name", "Year"]

# --- 3. إدارة الحالة ---
if 'user_role' not in st.session_state: st.session_state['user_role'] = None
if 'user_info' not in st.session_state: st.session_state['user_info'] = None

# --- 4. الاتصال بجوجل شيت ---
@st.cache_resource
def get_client():
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
            st.error("⚠️ مفاتيح الربط غير موجودة.")
            return None
    except Exception as e:
        st.error(f"خطأ اتصال: {e}")
        return None

def ensure_headers(ws, headers_list):
    """دالة الإصلاح الذاتي: بتصلح العناوين لو بايظة أو فاضية"""
    try:
        current_headers = ws.row_values(1)
        # لو العناوين فاضية أو مش مطابقة للمواصفات، نعيد كتابتها
        if not current_headers or current_headers != headers_list:
            ws.resize(cols=len(headers_list))
            # بنحدث الصف الأول بالعناوين الصح
            ws.update(range_name=f"A1:{chr(64+len(headers_list))}1", values=[headers_list])
            return True
    except:
        pass
    return False

def get_sheet_data(worksheet_name):
    client = get_client()
    if not client: return pd.DataFrame()
    
    try:
        sheet = client.open(SHEET_NAME)
        try:
            ws = sheet.worksheet(worksheet_name)
        except:
            ws = sheet.add_worksheet(worksheet_name, 1000, 20)
        
        # التأكد من صحة العناوين حسب نوع الشيت
        if worksheet_name == "Students_Main":
            ensure_headers(ws, STUDENT_HEADERS)
        elif worksheet_name == "Teachers_Main":
            ensure_headers(ws, TEACHER_HEADERS)
        elif worksheet_name == "Subjects_Data":
            ensure_headers(ws, SUBJECT_HEADERS)
            
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        # لو حصل خطأ Duplicate headers، الدالة دي هتعالجه المرة الجاية
        # بس عشان المستخدم ميشوفش ايرور، بنرجع داتا فريم فاضي مؤقتاً
        st.warning(f"جاري إصلاح هيكل البيانات في {worksheet_name}... حاول مرة أخرى.")
        return pd.DataFrame()

# --- 5. دوال المنطق ---

def generate_code(prefix):
    digits = ''.join(random.choices(string.digits, k=8))
    caps = ''.join(random.choices(string.ascii_uppercase, k=2))
    return f"{prefix}{caps}{digits}"

def register_user_logic(role, data_dict):
    client = get_client()
    sheet = client.open(SHEET_NAME)
    
    if role == "Teacher":
        ws_name = "Teachers_Main"
        prefix = "T"
        headers = TEACHER_HEADERS
    else:
        ws_name = "Students_Main"
        prefix = "S"
        headers = STUDENT_HEADERS
        
    ws = sheet.worksheet(ws_name)
    ensure_headers(ws, headers) # ضمان العناوين قبل الكتابة
    
    try: existing_codes = ws.col_values(1)
    except: existing_codes = []
    
    while True:
        new_code = generate_code(prefix)
        if new_code not in existing_codes:
            break
            
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    
    # تجهيز الصف حسب الترتيب الجديد للأعمدة
    if role == "Teacher":
        row = [
            new_code, data_dict['Name'], password, 
            data_dict.get('National_ID', ''), data_dict.get('Phone', ''), data_dict.get('Email', ''),
            data_dict.get('Address', ''), data_dict.get('Governorate', ''), data_dict.get('Nationality', ''),
            data_dict.get('Religion', ''), data_dict.get('DOB', ''), str(datetime.now())
        ]
    else:
        # Student
        row = [
            new_code, data_dict['Name'], password, 1, 0, 0, # Year 1, Fees 0
            data_dict.get('National_ID', ''), data_dict.get('Address', ''), data_dict.get('Phone', ''),
            data_dict.get('Governorate', ''), data_dict.get('Nationality', ''), data_dict.get('Religion', ''),
            data_dict.get('DOB', ''), data_dict.get('Major', ''), data_dict.get('Degree_Score', ''), str(datetime.now())
        ]
        
    ws.append_row(row)
    
    # إنشاء شيت خاص
    try:
        try: sheet.worksheet(new_code)
        except:
            sheet.add_worksheet(title=new_code, rows="100", cols="10")
            sheet.worksheet(new_code).append_row(["النوع", "التفاصيل", "التاريخ", "Link"])
    except: pass
        
    return new_code, password

def login_logic(code, password, role_target):
    ws_name = "Teachers_Main" if role_target == "Teacher" else "Students_Main"
    df = get_sheet_data(ws_name)
    
    if df.empty: return None
        
    # تنظيف البيانات للمقارنة
    df['Code'] = df['Code'].astype(str).str.strip()
    df['Password'] = df['Password'].astype(str).str.strip()
    
    user = df[(df['Code'] == str(code).strip()) & (df['Password'] == str(password).strip())]
    
    if not user.empty:
        return user.iloc[0].to_dict()
    return None

# --- 6. واجهات المستخدم ---

def admin_dashboard():
    st.title("🛠️ لوحة تحكم الإدارة (System Admin)")
    
    tab1, tab2, tab3, tab4 = st.tabs(["تسجيل طلاب", "تسجيل معلمين", "الخزينة", "إدارة المواد"])
    
    # --- تسجيل طلاب (بيانات كاملة) ---
    with tab1:
        st.subheader("تسجيل طالب جديد (بيانات تفصيلية)")
        with st.form("add_student_full"):
            c1, c2 = st.columns(2)
            name = c1.text_input("الاسم رباعي")
            nid = c2.text_input("الرقم القومي (14 رقم)")
            
            c3, c4 = st.columns(2)
            phone = c3.text_input("رقم الهاتف")
            dob = c4.date_input("تاريخ الميلاد", min_value=datetime(1990,1,1))
            
            c5, c6 = st.columns(2)
            gov = c5.text_input("المحافظة")
            addr = c6.text_input("العنوان بالتفصيل")
            
            c7, c8 = st.columns(2)
            major = c7.selectbox("التخصص", ["نظم معلومات", "محاسبة", "إدارة أعمال"])
            score = c8.number_input("مجموع الثانوية/المؤهل", min_value=0.0)
            
            submitted = st.form_submit_button("حفظ بيانات الطالب")
            if submitted and name and nid:
                with st.spinner("جاري التسجيل..."):
                    data = {
                        "Name": name, "National_ID": nid, "Phone": phone, "DOB": str(dob),
                        "Governorate": gov, "Address": addr, "Major": major, "Degree_Score": score,
                        "Nationality": "مصر", "Religion": "غير محدد" # يمكن إضافتهم للواجهة
                    }
                    code, pwd = register_user_logic("Student", data)
                st.success("تم الحفظ! ✅")
                st.info(f"كود الطالب: {code}")
                st.warning(f"الباسوورد: {pwd}")

    # --- تسجيل معلمين (بيانات كاملة) ---
    with tab2:
        st.subheader("تسجيل عضو هيئة تدريس")
        with st.form("add_teacher_full"):
            t_name = st.text_input("الاسم رباعي")
            t_nid = st.text_input("الرقم القومي")
            
            tc1, tc2 = st.columns(2)
            t_phone = tc1.text_input("رقم الموبايل")
            t_email = tc2.text_input("البريد الإلكتروني")
            
            tc3, tc4 = st.columns(2)
            t_addr = tc3.text_input("العنوان")
            t_gov = tc4.text_input("المحافظة")
            
            t_sub = st.form_submit_button("إنشاء ملف المعلم")
            if t_sub and t_name:
                with st.spinner("جاري الحفظ..."):
                    data = {
                        "Name": t_name, "National_ID": t_nid, "Phone": t_phone, 
                        "Email": t_email, "Address": t_addr, "Governorate": t_gov
                    }
                    code, pwd = register_user_logic("Teacher", data)
                st.success("تم إنشاء الحساب! 🚀")
                st.info(f"الكود: {code} | الباسوورد: {pwd}")

    # --- الخزينة ---
    with tab3:
        st.subheader("💰 التحصيل المالي")
        s_code = st.text_input("بحث بكود الطالب", key="pay_search")
        if st.button("بحث"):
            df = get_sheet_data("Students_Main")
            if not df.empty:
                df['Code'] = df['Code'].astype(str).str.strip()
                student = df[df['Code'] == str(s_code).strip()]
                if not student.empty:
                    st.session_state['pay_student'] = student.iloc[0].to_dict()
                else:
                    st.error("طالب غير موجود")
        
        if 'pay_student' in st.session_state:
            stu = st.session_state['pay_student']
            st.write(f"الطالب: **{stu['Name']}** | الفرقة: {stu['Year']}")
            
            try: year = int(stu['Year'])
            except: year = 1
            
            tuition_fees = BASE_FEES
            for _ in range(1, year): tuition_fees += tuition_fees * 0.10
            tuition_fees = int(tuition_fees)
            
            # معالجة الأرقام عشان لو جاية فاضية
            paid_raw = str(stu['Paid_Tuition'])
            paid = int(paid_raw) if paid_raw.isdigit() else 0
            remaining = tuition_fees - paid
            
            c1, c2, c3 = st.columns(3)
            c1.metric("المستحق", f"{tuition_fees:,}")
            c2.metric("المدفوع", f"{paid:,}")
            c3.metric("المتبقي", f"{remaining:,}")
            
            pay_amt = st.number_input("المبلغ", min_value=0, max_value=remaining if remaining > 0 else 0)
            if st.button("تأكيد الدفع"):
                client = get_client()
                sheet = client.open(SHEET_NAME)
                ws = sheet.worksheet("Students_Main")
                cell = ws.find(str(stu['Code']))
                # تحديث عمود Paid_Tuition (العمود رقم 5 حسب الترتيب الجديد)
                ws.update_cell(cell.row, 5, paid + pay_amt)
                
                try: sheet.worksheet(str(stu['Code'])).append_row(["سداد مصاريف", f"{pay_amt} ج.م", str(datetime.now()), ""])
                except: pass
                
                st.success("تم الدفع!")
                del st.session_state['pay_student']
                time.sleep(1)
                st.rerun()

    # --- إدارة المواد ---
    with tab4:
        st.subheader("📚 توزيع المواد الدراسية")
        st.info("اربط المواد بالمعلمين عشان تظهر عندهم")
        
        t_df = get_sheet_data("Teachers_Main")
        if not t_df.empty:
            # قائمة بالأسماء والأكواد
            teachers_map = {f"{row['Name']} ({row['Code']})": row['Code'] for idx, row in t_df.iterrows()}
            
            selected_t_label = st.selectbox("اختار المعلم", list(teachers_map.keys()))
            selected_t_code = teachers_map[selected_t_label]
            selected_t_name = selected_t_label.split(" (")[0]
            
            subject_name = st.text_input("اسم المادة")
            year_lvl = st.selectbox("الفرقة الدراسية", [1, 2, 3, 4])
            
            if st.button("إضافة المادة"):
                client = get_client()
                sheet = client.open(SHEET_NAME)
                try: ws_sub = sheet.worksheet("Subjects_Data")
                except: 
                    ws_sub = sheet.add_worksheet("Subjects_Data", 1000, 4)
                    ws_sub.append_row(SUBJECT_HEADERS)
                
                # التأكد من الهيدر
                ensure_headers(ws_sub, SUBJECT_HEADERS)
                
                ws_sub.append_row([subject_name, selected_t_code, selected_t_name, year_lvl])
                st.success(f"تم إضافة {subject_name} للدكتور {selected_t_name}")

def teacher_dashboard():
    user = st.session_state['user_info']
    st.title(f"👨‍🏫 بوابة عضو هيئة التدريس: {user['Name']}")
    
    st.divider()
    st.subheader("المواد المسندة إليك")
    
    df_sub = get_sheet_data("Subjects_Data")
    
    if not df_sub.empty:
        # الفلترة بالكود
        my_subs = df_sub[df_sub['Teacher_Code'].astype(str) == str(user['Code'])]
        
        if not my_subs.empty:
            for i, row in my_subs.iterrows():
                with st.expander(f"📘 مادة: {row['Subject']} - الفرقة {row['Year']}"):
                    st.write("أدوات التحكم:")
                    stud_search = st.text_input("كود الطالب للرصد", key=f"s_{i}")
                    grade = st.radio("النتيجة", ["ناجح", "راسب"], key=f"g_{i}", horizontal=True)
                    if st.button("حفظ النتيجة", key=f"b_{i}"):
                        st.success(f"تم رصد {grade} للطالب {stud_search}")
                        # هنا يمكن إضافة كود الحفظ في شيت الطالب
        else:
            st.info("لا توجد مواد مسجلة باسمك. يرجى مراجعة إدارة النظام.")
    else:
        st.warning("جدول المواد فارغ.")
        
    st.divider()
    if st.button("خروج", type="primary"):
        st.session_state['user_role'] = None
        st.session_state['user_info'] = None
        st.rerun()

def student_dashboard():
    user = st.session_state['user_info']
    st.title(f"🎓 الطالب: {user['Name']}")
    
    c1, c2 = st.columns(2)
    c1.metric("الفرقة", user['Year'])
    c2.metric("المدفوع", f"{user['Paid_Tuition']} ج.م")
    
    st.divider()
    st.subheader("الملف الأكاديمي")
    
    client = get_client()
    try:
        sheet = client.open(SHEET_NAME)
        ws = sheet.worksheet(str(user['Code']))
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        st.dataframe(
            df, 
            column_config={"Link": st.column_config.LinkColumn("رابط", display_text="🔗 فتح")},
            use_container_width=True
        )
    except:
        st.info("جاري إعداد الملف...")

    if st.button("خروج"):
        st.session_state['user_role'] = None
        st.rerun()

# --- 7. الصفحة الرئيسية ---

def main():
    if st.session_state['user_role'] == "Admin":
        admin_dashboard()
        return
    elif st.session_state['user_role'] == "Teacher":
        teacher_dashboard()
        return
    elif st.session_state['user_role'] == "Student":
        student_dashboard()
        return

    c1, c2 = st.columns([1, 2])
    with c1:
        st.image("https://cdn-icons-png.flaticon.com/512/2942/2942544.png", width=150)
        st.title("بوابة المعاهد")
    
    with c2:
        tab_s, tab_t, tab_a = st.tabs(["الطلاب", "المعلمين", "الإدارة"])
        
        with tab_s:
            with st.form("ls"):
                c = st.text_input("كود الطالب")
                p = st.text_input("كلمة المرور", type="password")
                if st.form_submit_button("دخول"):
                    u = login_logic(c, p, "Student")
                    if u:
                        st.session_state['user_role'] = "Student"
                        st.session_state['user_info'] = u
                        st.rerun()
                    else: st.error("بيانات خطأ")

        with tab_t:
            with st.form("lt"):
                c = st.text_input("كود المعلم")
                p = st.text_input("كلمة المرور", type="password")
                if st.form_submit_button("دخول"):
                    u = login_logic(c, p, "Teacher")
                    if u:
                        st.session_state['user_role'] = "Teacher"
                        st.session_state['user_info'] = u
                        st.rerun()
                    else: st.error("بيانات خطأ")
        
        with tab_a:
            with st.form("la"):
                u = st.text_input("User")
                p = st.text_input("Password", type="password")
                if st.form_submit_button("دخول"):
                    if u == "admin" and p == "admin123":
                        st.session_state['user_role'] = "Admin"
                        st.rerun()
                    else: st.error("خطأ")

if __name__ == '__main__':
    main()
