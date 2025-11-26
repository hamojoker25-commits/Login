import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random
import string
from datetime import datetime
import time

# --- 1. إعدادات الصفحة والتصميم ---
st.set_page_config(page_title="نظام المعاهد العليا الذكي", layout="wide", page_icon="🎓")

# --- 2. ثوابت النظام ---
SHEET_NAME = "users_database"
BASE_FEES = 18000
BOOK_FEES = {1: 2000, 2: 2500, 3: 3000, 4: 3500}

# --- 3. إدارة الحالة (Session State) ---
# بنستخدم ده عشان نحفظ مين مسجل دخول والبيانات ماتضعش لما الصفحة تعمل Refresh
if 'user_role' not in st.session_state: st.session_state['user_role'] = None
if 'user_info' not in st.session_state: st.session_state['user_info'] = None

# --- 4. الاتصال بجوجل شيت (Backend) ---
@st.cache_resource
def get_client():
    """دالة تتصل بجوجل مرة واحدة فقط لسرعة الأداء"""
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
            st.error("⚠️ بيانات الربط (Secrets) غير موجودة.")
            return None
    except Exception as e:
        st.error(f"خطأ تقني في الاتصال: {e}")
        return None

def get_sheet_data(worksheet_name):
    """جلب البيانات طازجة (بدون تخزين مؤقت) لحل مشكلة اختفاء البيانات"""
    client = get_client()
    if not client: return pd.DataFrame()
    
    try:
        sheet = client.open(SHEET_NAME)
        # التأكد من وجود الشيت وإنشاؤه لو مش موجود
        try:
            ws = sheet.worksheet(worksheet_name)
        except:
            ws = sheet.add_worksheet(worksheet_name, 1000, 20)
            # إضافة العناوين الافتراضية حسب النوع
            if worksheet_name == "Teachers_Main":
                ws.append_row(["Code", "Name", "Password", "Subject", "Data"])
            elif worksheet_name == "Students_Main":
                ws.append_row(["Code", "Name", "Password", "Year", "Paid_Tuition", "Paid_Books", "Data"])
            elif worksheet_name == "Subjects_Data":
                ws.append_row(["Subject", "Teacher_Code", "Year"])
        
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"خطأ في قراءة {worksheet_name}: {e}")
        return pd.DataFrame()

# --- 5. دوال المنطق والعمليات ---

def generate_code(prefix):
    """توليد كود عشوائي قوي"""
    digits = ''.join(random.choices(string.digits, k=8))
    caps = ''.join(random.choices(string.ascii_uppercase, k=2))
    return f"{prefix}{caps}{digits}"  # مثال: TEA12345678

def register_user_logic(role, data_dict):
    client = get_client()
    sheet = client.open(SHEET_NAME)
    
    if role == "Teacher":
        ws_name = "Teachers_Main"
        prefix = "T"
    else:
        ws_name = "Students_Main"
        prefix = "S"
        
    ws = sheet.worksheet(ws_name)
    
    # التأكد من عدم تكرار الكود
    try: existing_codes = ws.col_values(1)
    except: existing_codes = []
    
    while True:
        new_code = generate_code(prefix)
        if new_code not in existing_codes:
            break
            
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    
    # حفظ البيانات
    if role == "Teacher":
        # Code, Name, Password, Subject, Data(JSON)
        row = [new_code, data_dict['name'], password, "", str(data_dict)]
    else:
        # Code, Name, Password, Year, Paid_T, Paid_B, Data(JSON)
        # Year=1 (الفرقة الأولى), المدفوع=0
        row = [new_code, data_dict['name'], password, 1, 0, 0, str(data_dict)]
        
    ws.append_row(row)
    
    # إنشاء شيت خاص
    try:
        sheet.add_worksheet(title=new_code, rows="100", cols="10")
        sheet.worksheet(new_code).append_row(["النوع", "التفاصيل", "التاريخ", "Link"])
    except:
        pass
        
    return new_code, password

def login_logic(code, password, role_target):
    """نظام تسجيل دخول صارم يحل مشكلة عدم الفتح"""
    if role_target == "Teacher":
        df = get_sheet_data("Teachers_Main")
    else:
        df = get_sheet_data("Students_Main")
        
    if df.empty:
        return None
        
    # تنظيف البيانات (أهم خطوة لحل مشكلتك)
    # بنحول كل حاجة لنص وبنشيل المسافات
    df['Code'] = df['Code'].astype(str).str.strip()
    df['Password'] = df['Password'].astype(str).str.strip()
    code_input = str(code).strip()
    pass_input = str(password).strip()
    
    user = df[(df['Code'] == code_input) & (df['Password'] == pass_input)]
    
    if not user.empty:
        return user.iloc[0].to_dict()
    return None

# --- 6. واجهات المستخدم (Front-End) ---

def admin_dashboard():
    st.title("🛠️ لوحة تحكم الإدارة (الكونترول)")
    
    tab1, tab2, tab3, tab4 = st.tabs(["تسجيل طلاب", "تسجيل معلمين", "الخزينة", "إدارة المواد"])
    
    # --- تسجيل طلاب ---
    with tab1:
        st.subheader("إضافة طالب جديد")
        with st.form("add_student"):
            c1, c2 = st.columns(2)
            name = c1.text_input("الاسم رباعي")
            nid = c2.text_input("الرقم القومي")
            major = st.selectbox("التخصص", ["نظم معلومات", "محاسبة", "إدارة"])
            # (يمكنك إضافة باقي الحقول هنا)
            submitted = st.form_submit_button("تسجيل الطالب")
            if submitted and name and nid:
                with st.spinner("جاري التسجيل..."):
                    data = {"name": name, "nid": nid, "major": major, "join_date": str(datetime.now())}
                    code, pwd = register_user_logic("Student", data)
                st.success("تم الحفظ بنجاح! ✅")
                st.info(f"كود الطالب: {code}")
                st.warning(f"كلمة المرور: {pwd}")

    # --- تسجيل معلمين (تم حل المشكلة هنا) ---
    with tab2:
        st.subheader("إضافة عضو هيئة تدريس")
        with st.form("add_teacher"):
            t_name = st.text_input("اسم المعلم")
            t_nid = st.text_input("الرقم القومي")
            t_phone = st.text_input("رقم الهاتف")
            t_email = st.text_input("البريد الإلكتروني")
            submitted_t = st.form_submit_button("تسجيل المعلم")
            
            if submitted_t and t_name:
                with st.spinner("جاري إنشاء الملف..."):
                    data = {"name": t_name, "nid": t_nid, "phone": t_phone, "email": t_email}
                    code, pwd = register_user_logic("Teacher", data)
                st.success("تم إنشاء حساب المعلم! 🚀")
                st.markdown(f"""
                ### 📌 بيانات الدخول (هام جداً):
                - **الكود:** `{code}`
                - **الباسوورد:** `{pwd}`
                *(يرجى نسخ هذه البيانات الآن)*
                """)

    # --- الخزينة ---
    with tab3:
        st.subheader("💰 تحصيل المصروفات")
        s_code = st.text_input("ابحث بكود الطالب", key="pay_search")
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
            
            # العمليات الحسابية
            try: year = int(stu['Year'])
            except: year = 1
            
            tuition_fees = BASE_FEES
            for _ in range(1, year): tuition_fees += tuition_fees * 0.10
            tuition_fees = int(tuition_fees)
            
            paid = int(stu['Paid_Tuition']) if str(stu['Paid_Tuition']).isdigit() else 0
            remaining = tuition_fees - paid
            
            c1, c2, c3 = st.columns(3)
            c1.metric("المستحق", f"{tuition_fees:,}")
            c2.metric("المدفوع", f"{paid:,}")
            c3.metric("المتبقي", f"{remaining:,}", delta_color="inverse")
            
            pay_amt = st.number_input("المبلغ للدفع", min_value=0, max_value=remaining if remaining > 0 else 0)
            if st.button("تأكيد الدفع"):
                client = get_client()
                sheet = client.open(SHEET_NAME)
                ws = sheet.worksheet("Students_Main")
                cell = ws.find(str(stu['Code']))
                # تحديث الخلية (العمود 5 للمصاريف)
                ws.update_cell(cell.row, 5, paid + pay_amt)
                
                # إضافة إيصال في شيت الطالب
                try:
                    sheet.worksheet(str(stu['Code'])).append_row(["سداد مصاريف", f"{pay_amt} ج.م", str(datetime.now()), ""])
                except: pass
                
                st.success("تم الدفع بنجاح!")
                del st.session_state['pay_student']
                st.rerun()

    # --- إدارة المواد ---
    with tab4:
        st.subheader("📚 ربط المواد بالمعلمين")
        st.info("هنا بنحدد مين بيدرس إيه عشان يظهر في صفحة المعلم")
        
        # جلب المعلمين للاختيار
        teachers_df = get_sheet_data("Teachers_Main")
        if not teachers_df.empty:
            t_dict = dict(zip(teachers_df['Name'], teachers_df['Code']))
            selected_t_name = st.selectbox("اختار المعلم", list(t_dict.keys()))
            subject_name = st.text_input("اسم المادة")
            year_level = st.selectbox("للفرقة", [1, 2, 3, 4])
            
            if st.button("إسناد المادة"):
                client = get_client()
                sheet = client.open(SHEET_NAME)
                try: ws_sub = sheet.worksheet("Subjects_Data")
                except: ws_sub = sheet.add_worksheet("Subjects_Data", 1000, 3)
                
                ws_sub.append_row([subject_name, t_dict[selected_t_name], year_level])
                st.success(f"تم إسناد مادة {subject_name} للمعلم {selected_t_name}")

def teacher_dashboard():
    user = st.session_state['user_info']
    st.title(f"👨‍🏫 بوابة عضو هيئة التدريس: {user['Name']}")
    st.write(f"كود المعلم: `{user['Code']}`")
    
    st.divider()
    st.subheader("📋 موادي الدراسية")
    
    # جلب المواد الخاصة بهذا المعلم
    df_sub = get_sheet_data("Subjects_Data")
    if not df_sub.empty:
        # فلترة المواد
        my_subjects = df_sub[df_sub['Teacher_Code'].astype(str) == str(user['Code'])]
        
        if not my_subjects.empty:
            for idx, row in my_subjects.iterrows():
                with st.expander(f"مادة: {row['Subject']} (الفرقة {row['Year']})"):
                    st.write("أدوات التحكم:")
                    # هنا ممكن نضيف أدوات رصد الدرجات
                    st.text_input(f"بحث عن طالب في {row['Subject']}", key=f"search_{idx}")
                    st.button(f"رصد درجات {row['Subject']}", key=f"btn_{idx}")
        else:
            st.info("لا توجد مواد مسندة إليك حالياً. تواصل مع الإدارة.")
    else:
        st.warning("لم يتم إعداد جدول المواد بعد.")
        
    st.divider()
    if st.button("تسجيل الخروج", type="primary"):
        st.session_state['user_role'] = None
        st.session_state['user_info'] = None
        st.rerun()

def student_dashboard():
    user = st.session_state['user_info']
    st.title(f"🎓 بوابة الطالب: {user['Name']}")
    
    col1, col2 = st.columns(2)
    col1.metric("الفرقة الدراسية", user['Year'])
    
    # جلب البيانات المالية
    try: year = int(user['Year'])
    except: year = 1
    total_fees = BASE_FEES
    for _ in range(1, year): total_fees += total_fees * 0.10
    total_fees = int(total_fees)
    paid = int(user['Paid_Tuition']) if str(user['Paid_Tuition']).isdigit() else 0
    
    col2.metric("الموقف المالي", f"{total_fees - paid} ج.م (متبقي)")
    
    st.divider()
    st.subheader("📂 ملفك الشخصي")
    
    # عرض الشيت الخاص
    client = get_client()
    try:
        sheet = client.open(SHEET_NAME)
        ws = sheet.worksheet(str(user['Code']))
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        # تحويل الروابط لأزرار
        st.dataframe(
            df, 
            column_config={"Link": st.column_config.LinkColumn("رابط", display_text="🔗 فتح")},
            use_container_width=True
        )
    except:
        st.info("الملف الشخصي قيد الإعداد...")

    st.divider()
    if st.button("تسجيل الخروج", type="primary"):
        st.session_state['user_role'] = None
        st.session_state['user_info'] = None
        st.rerun()

# --- 7. الصفحة الرئيسية (المدخل) ---

def main():
    # لو المستخدم مسجل دخول، نوجهه لصفحته علطول
    if st.session_state['user_role'] == "Admin":
        admin_dashboard()
        return
    elif st.session_state['user_role'] == "Teacher":
        teacher_dashboard()
        return
    elif st.session_state['user_role'] == "Student":
        student_dashboard()
        return

    # صفحة تسجيل الدخول (Landing Page)
    c1, c2 = st.columns([1, 2])
    
    with c1:
        st.image("https://cdn-icons-png.flaticon.com/512/2942/2942544.png", width=150)
        st.title("بوابة المعاهد")
        st.write("نظام الإدارة الإلكتروني الموحد")
    
    with c2:
        tab_login_s, tab_login_t, tab_login_a = st.tabs(["دخول الطلاب", "دخول المعلمين", "الإدارة"])
        
        with tab_login_s:
            with st.form("login_s"):
                code_s = st.text_input("كود الطالب")
                pass_s = st.text_input("كلمة المرور", type="password")
                if st.form_submit_button("دخول 🎓"):
                    user = login_logic(code_s, pass_s, "Student")
                    if user:
                        st.session_state['user_role'] = "Student"
                        st.session_state['user_info'] = user
                        st.success("تم الدخول بنجاح!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("بيانات غير صحيحة")

        with tab_login_t:
            with st.form("login_t"):
                code_t = st.text_input("كود المعلم")
                pass_t = st.text_input("كلمة المرور", type="password")
                if st.form_submit_button("دخول 👨‍🏫"):
                    user = login_logic(code_t, pass_t, "Teacher")
                    if user:
                        st.session_state['user_role'] = "Teacher"
                        st.session_state['user_info'] = user
                        st.success("أهلاً بك يا دكتور!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("بيانات غير صحيحة")
        
        with tab_login_a:
            with st.form("login_a"):
                user_a = st.text_input("اسم المستخدم")
                pass_a = st.text_input("كلمة المرور", type="password")
                if st.form_submit_button("دخول الإدارة 🔒"):
                    # باسوورد ثابت للإدارة (ممكن تغيره)
                    if user_a == "admin" and pass_a == "admin123":
                        st.session_state['user_role'] = "Admin"
                        st.rerun()
                    else:
                        st.error("خطأ في صلاحيات الإدارة")

if __name__ == '__main__':
    main()
