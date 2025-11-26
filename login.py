import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random
import string
from datetime import datetime
import time

# --- إعدادات الصفحة ---
st.set_page_config(page_title="نظام المعاهد العليا", layout="wide", page_icon="🎓")

# --- ثوابت النظام ---
SHEET_NAME = "users_database"
BASE_FEES = 18000
BOOK_FEES = {1: 2000, 2: 2500, 3: 3000, 4: 3500}

# --- تهيئة الـ Session State (لحل مشكلة إعادة التحميل) ---
if 'logged_in_student' not in st.session_state:
    st.session_state['logged_in_student'] = None
if 'logged_in_teacher' not in st.session_state:
    st.session_state['logged_in_teacher'] = None
if 'current_menu' not in st.session_state:
    st.session_state['current_menu'] = "الرئيسية"

# --- الاتصال بجوجل شيت ---
@st.cache_resource
def connect_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            return client.open(SHEET_NAME)
        else:
            st.error("⚠️ لم يتم العثور على مفاتيح الربط في Secrets")
            return None
    except Exception as e:
        st.error(f"خطأ في الاتصال: {e}")
        return None

# --- دوال مساعدة (Safe Functions لمنع الـ ValueError) ---
def safe_int(value):
    """تحويل آمن للنصوص إلى أرقام صحيحة"""
    try:
        return int(float(str(value).replace(',', '').strip()))
    except:
        return 0

def get_data(sheet_obj, worksheet_name):
    try:
        ws = sheet_obj.worksheet(worksheet_name)
        return pd.DataFrame(ws.get_all_records())
    except:
        return pd.DataFrame()

def generate_code(prefix, length):
    digits = ''.join(random.choices(string.digits, k=length))
    if prefix == "T": # معلم: حرفين كابتل + 8 أرقام
        caps = ''.join(random.choices(string.ascii_uppercase, k=2))
        return caps + digits
    elif prefix == "S": # طالب: حرف كابتل + 7 أرقام
        cap = random.choice(string.ascii_uppercase)
        return cap + digits
    return digits

def calculate_tuition(year):
    fees = BASE_FEES
    # حساب مركب: كل سنة تزيد 10% عن السنة السابقة
    for _ in range(1, safe_int(year)):
        fees += fees * 0.10
    return int(fees)

# --- الوظائف الرئيسية ---

def register_student(data_dict, sheet):
    ws_main = sheet.worksheet("Students_Main")
    try:
        existing_codes = ws_main.col_values(1)
    except:
        existing_codes = []
    
    while True:
        new_code = generate_code("S", 7)
        if new_code not in existing_codes:
            break
            
    password = generate_code("S", 7)
    
    # الترتيب مهم جداً عشان الخزينة تقرأ صح
    # Paid_Tuition رقم 18 (index 17) | Paid_Books رقم 19 (index 18)
    row = [
        new_code, data_dict['name'], password, data_dict['dob'], data_dict['gov'], 
        data_dict['address'], data_dict['nat'], data_dict['nid'], data_dict['nid_source'],
        data_dict['religion'], data_dict['cert'], data_dict['cert_date'], data_dict['seat_num'],
        data_dict['total_score'], data_dict['major'], 1, # Year
        str(datetime.now()), 0, 0, "{}" # Paid Tuition, Paid Books, Subjects JSON
    ]
    ws_main.append_row(row)
    
    try:
        ws_user = sheet.add_worksheet(title=new_code, rows="100", cols="10")
        ws_user.append_row(["البيان", "التفاصيل", "الرابط/ملاحظات", "التاريخ"])
        ws_user.append_row(["تنبيه", "أي تعديلات هنا تتم بمعرفة IT", "", str(datetime.now())])
    except:
        pass
        
    return new_code, password

def register_teacher(data_dict, sheet):
    try:
        ws_main = sheet.worksheet("Teachers_Main")
    except:
        ws_main = sheet.add_worksheet("Teachers_Main", 1000, 20)
        ws_main.append_row(["Code", "Name", "Password", "DOB", "Nat", "Religion", "Gov", "Address", "Email", "NID", "NID_Source"])

    try:
        existing_codes = ws_main.col_values(1)
    except:
        existing_codes = []

    while True:
        # كود المعلم: حرفين كابتل + 8 أرقام
        digits = ''.join(random.choices(string.digits, k=8))
        caps = ''.join(random.choices(string.ascii_uppercase, k=2))
        new_code = caps + digits
        if new_code not in existing_codes:
            break
            
    # باسوورد المعلم (حرفين و8 أرقام مختلفين عن الكود)
    pwd_digits = ''.join(random.choices(string.digits, k=8))
    pwd_caps = ''.join(random.choices(string.ascii_uppercase, k=2))
    password = pwd_caps + pwd_digits
    
    row = [
        new_code, data_dict['name'], password, data_dict['dob'], data_dict['nat'],
        data_dict['religion'], data_dict['gov'], data_dict['address'], 
        data_dict['email'], data_dict['nid'], data_dict['nid_source']
    ]
    ws_main.append_row(row)
    
    # إنشاء شيت خاص للمعلم
    try:
        sheet.add_worksheet(title=new_code, rows="100", cols="10")
        sheet.worksheet(new_code).append_row(["الملاحظات", "التاريخ"])
    except:
        pass
        
    return new_code, password

def process_payment(student_code, amount, pay_type, visa_details, sheet, payment_category="tuition"):
    ws = sheet.worksheet("Students_Main")
    cell = ws.find(student_code)
    row_num = cell.row
    
    # استخدام safe_int لمنع الـ ValueError
    col_idx = 18 if payment_category == "tuition" else 19
    current_val_raw = ws.cell(row_num, col_idx).value
    current_val = safe_int(current_val_raw)
    
    new_val = current_val + safe_int(amount)
    ws.update_cell(row_num, col_idx, new_val)
    
    # تسجيل في شيت الطالب
    try:
        ws_student = sheet.worksheet(student_code)
        note = f"دفع {payment_category} - {pay_type}"
        if pay_type == "فيزا" and visa_details:
            note += f" (Visa Ends: {visa_details[-4:]})"
        
        ws_student.append_row(["عملية دفع", f"{amount} ج.م", note, str(datetime.now())])
    except:
        pass # لو شيت الطالب مش موجود لسبب ما
    return True

# --- الواجهة الرئيسية ---

def main():
    sheet = connect_google_sheet()
    if not sheet:
        st.stop()
        
    # التأكد من وجود الشيتات الأساسية (الطلاب، المعلمين، المواد)
    try:
        sheet.worksheet("Students_Main")
    except:
        ws = sheet.add_worksheet("Students_Main", 1000, 25)
        ws.append_row(["Code", "Name", "Password", "DOB", "Gov", "Address", "Nat", "NID", "NID_Source", 
                       "Religion", "Cert", "Cert_Date", "Seat_Num", "Score", "Major", "Year", 
                       "Join_Date", "Paid_Tuition", "Paid_Books", "Subjects_Status"])
    
    try:
        sheet.worksheet("Subjects_Data")
    except:
        ws_sub = sheet.add_worksheet("Subjects_Data", 1000, 5)
        ws_sub.append_row(["Subject_Name", "Year", "Term", "Teacher_Code"])

    # القائمة الجانبية (Navigation)
    st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2942/2942544.png", width=100)
    st.sidebar.title("نظام المعاهد العليا")
    
    # استخدام Session State للتحكم في القائمة عشان الصفحة ما تعملش Reload وترجع للأول
    menu_options = ["الرئيسية", "شؤون الطلاب (تسجيل)", "شؤون المعلمين", "الخزينة (دفع المصاريف)", "بوابة الطالب", "بوابة المعلم", "البحث والاستعلام"]
    
    # زرار للقائمة
    selected_menu = st.sidebar.radio("القائمة", menu_options, index=menu_options.index(st.session_state['current_menu']))
    
    # تحديث الحالة لو المستخدم اختار حاجة جديدة
    if selected_menu != st.session_state['current_menu']:
        st.session_state['current_menu'] = selected_menu
        st.rerun()

    menu = st.session_state['current_menu']

    if menu == "الرئيسية":
        st.title("🏛️ نظام إدارة المعاهد العليا")
        st.info("مرحباً بك في النظام المتكامل.")
        
        c1, c2 = st.columns(2)
        with c1:
            st.metric("الطلاب", len(get_data(sheet, "Students_Main")))
        with c2:
            st.metric("المعلمين", len(get_data(sheet, "Teachers_Main")))

    # ------------------------- شؤون الطلاب -------------------------
    elif menu == "شؤون الطلاب (تسجيل)":
        st.header("📝 تسجيل طالب جديد")
        with st.form("new_student"):
            c1, c2 = st.columns(2)
            name = c1.text_input("الاسم كامل")
            dob = c2.date_input("تاريخ الميلاد", min_value=datetime(1990,1,1))
            
            c3, c4 = st.columns(2)
            gov = c3.text_input("المحافظة")
            address = c4.text_input("العنوان")
            
            c5, c6 = st.columns(2)
            nat = c5.text_input("الجنسية", "مصر")
            religion = c6.selectbox("الديانة", ["مسلم", "مسيحي", "أخرى"])
            
            c7, c8 = st.columns(2)
            nid = c7.text_input("الرقم القومي (14 رقم)")
            nid_src = c8.text_input("جهة الإصدار")
            
            st.markdown("---")
            st.subheader("بيانات المؤهل")
            cc1, cc2, cc3 = st.columns(3)
            cert = cc1.text_input("الشهادة الحاصل عليها")
            cert_date = cc2.date_input("تاريخ الشهادة")
            seat_num = cc3.text_input("رقم الجلوس")
            
            cc4, cc5 = st.columns(2)
            total = cc4.number_input("المجموع", min_value=0.0)
            major = cc5.selectbox("التخصص", ["نظم معلومات", "إدارة أعمال", "محاسبة"])
            
            submit = st.form_submit_button("حفظ وتسجيل")
            
            if submit:
                if name and nid:
                    data = {
                        "name": name, "dob": str(dob), "gov": gov, "address": address,
                        "nat": nat, "nid": nid, "nid_source": nid_src, "religion": religion,
                        "cert": cert, "cert_date": str(cert_date), "seat_num": seat_num,
                        "total_score": total, "major": major
                    }
                    with st.spinner("جاري التسجيل..."):
                        code, pwd = register_student(data, sheet)
                    
                    st.success("تم تسجيل الطالب بنجاح! ✅")
                    st.info(f"👤 كود الطالب: {code}")
                    st.warning(f"🔑 كلمة المرور: {pwd}")
                else:
                    st.error("يرجى إكمال البيانات الأساسية")

    # ------------------------- شؤون المعلمين (تعديل كامل) -------------------------
    elif menu == "شؤون المعلمين":
        st.header("👨‍🏫 تسجيل معلم جديد")
        st.caption("أدخل البيانات كاملة لإنشاء ملف المعلم")
        
        with st.form("new_teacher_full"):
            t1, t2 = st.columns(2)
            t_name = t1.text_input("الاسم كامل")
            t_dob = t2.date_input("تاريخ الميلاد", min_value=datetime(1960,1,1))
            
            t3, t4 = st.columns(2)
            t_nat = t3.text_input("الجنسية", "مصر")
            t_rel = t4.selectbox("الديانة", ["مسلم", "مسيحي"])
            
            t5, t6 = st.columns(2)
            t_gov = t5.text_input("المحافظة")
            t_addr = t6.text_input("العنوان")
            
            t7, t8 = st.columns(2)
            t_email = t7.text_input("البريد الإلكتروني")
            t_nid = t8.text_input("الرقم القومي")
            
            t_nid_src = st.text_input("جهة إصدار الرقم القومي")
            
            t_submit = st.form_submit_button("تسجيل المعلم")
            
            if t_submit:
                if t_name and t_nid:
                    data = {
                        "name": t_name, "dob": str(t_dob), "nat": t_nat, "religion": t_rel,
                        "gov": t_gov, "address": t_addr, "email": t_email, 
                        "nid": t_nid, "nid_source": t_nid_src
                    }
                    with st.spinner("جاري إنشاء حساب المعلم..."):
                        code, pwd = register_teacher(data, sheet)
                    st.success("تم تسجيل المعلم بنجاح! ✅")
                    st.info(f"👨‍🏫 كود المعلم: {code}")
                    st.warning(f"🔑 كلمة المرور: {pwd}")
                else:
                    st.error("الاسم والرقم القومي مطلوبان")

    # ------------------------- الخزينة (حل مشكلة ValueError) -------------------------
    elif menu == "الخزينة (دفع المصاريف)":
        st.header("💰 الخزينة")
        
        tab1, tab2 = st.tabs(["مصاريف دراسية", "كتب دراسية"])
        
        with tab1:
            st.subheader("دفع المصاريف الدراسية")
            s_code = st.text_input("كود الطالب للبحث", key="search_fees")
            
            if s_code:
                df = get_data(sheet, "Students_Main")
                if not df.empty and 'Code' in df.columns:
                    # تحويل الكود لنص للمقارنة
                    df['Code'] = df['Code'].astype(str)
                    student = df[df['Code'] == str(s_code)]
                    
                    if not student.empty:
                        row_data = student.iloc[0]
                        st.success(f"الطالب: {row_data['Name']}")
                        
                        year = safe_int(row_data['Year'])
                        paid = safe_int(row_data['Paid_Tuition'])
                        
                        total_due = calculate_tuition(year)
                        remaining = total_due - paid
                        
                        c1, c2, c3 = st.columns(3)
                        c1.metric("الفرقة", year)
                        c2.metric("المستحق", f"{total_due:,}")
                        c3.metric("المتبقي", f"{remaining:,}", delta_color="inverse")
                        
                        pay_method = st.radio("طريقة الدفع", ["كاش", "فيزا"])
                        visa_info = ""
                        if pay_method == "فيزا":
                            v_num = st.text_input("رقم الفيزا (للتوثيق فقط)", type="password")
                            if v_num: visa_info = v_num
                            
                        amount = st.number_input("المبلغ", min_value=1, max_value=int(remaining) if remaining > 0 else 1000000)
                        
                        if st.button("تأكيد الدفع"):
                            if remaining <= 0:
                                st.warning("لا يوجد مستحقات.")
                            else:
                                process_payment(s_code, amount, pay_method, visa_info, sheet, "tuition")
                                st.balloons()
                                st.success("تم الدفع!")
                                time.sleep(1)
                                st.rerun()
                    else:
                        st.error("كود غير صحيح")
                else:
                    st.error("قاعدة البيانات فارغة أو بها مشكلة")

        with tab2:
            st.subheader("دفع مصاريف الكتب (كاش)")
            b_code = st.text_input("كود الطالب", key="book_fees")
            if b_code:
                df = get_data(sheet, "Students_Main")
                if not df.empty and 'Code' in df.columns:
                    df['Code'] = df['Code'].astype(str)
                    stud = df[df['Code'] == str(b_code)]
                    
                    if not stud.empty:
                        row = stud.iloc[0]
                        yr = safe_int(row['Year'])
                        book_fee = BOOK_FEES.get(yr, 0)
                        paid_book = safe_int(row['Paid_Books'])
                        
                        st.write(f"الطالب: {row['Name']} - الفرقة: {yr}")
                        
                        if paid_book >= book_fee:
                            st.success("✅ الكتب مدفوعة بالكامل.")
                            st.info(f"بيانات الدخول:\nالكود: {b_code}\nالباسوورد: {row['Password']}")
                        else:
                            st.metric("المطلوب للكتب", f"{book_fee} ج.م")
                            if st.button("تأكيد الدفع (كاش)"):
                                process_payment(b_code, book_fee, "Cash", "", sheet, "books")
                                st.success("تم الدفع!")
                                time.sleep(1)
                                st.rerun()

    # ------------------------- بوابة الطالب -------------------------
    elif menu == "بوابة الطالب":
        # لو مش مسجل دخول، اظهر شاشة الدخول
        if st.session_state['logged_in_student'] is None:
            st.header("🔐 دخول الطالب")
            code = st.text_input("كود الطالب")
            pas = st.text_input("كلمة المرور", type="password")
            
            if st.button("دخول"):
                df = get_data(sheet, "Students_Main")
                if not df.empty:
                    df['Code'] = df['Code'].astype(str)
                    df['Password'] = df['Password'].astype(str)
                    user = df[(df['Code'] == code) & (df['Password'] == pas)]
                    
                    if not user.empty:
                        st.session_state['logged_in_student'] = user.iloc[0].to_dict()
                        st.rerun()
                    else:
                        st.error("بيانات خطأ")
        else:
            # لو مسجل دخول، اظهر بياناته
            u = st.session_state['logged_in_student']
            st.title(f"مرحباً، {u['Name']}")
            
            # تحديث البيانات من الشيت مباشرة عشان لو حصل دفع
            # (اختياري: ممكن نعمل استعلام جديد هنا للتأكد من أحدث رصيد)
            
            yr = safe_int(u['Year'])
            total = calculate_tuition(yr)
            paid = safe_int(u['Paid_Tuition'])
            
            c1, c2, c3 = st.columns(3)
            c1.metric("الفرقة", yr)
            c2.metric("المدفوع", paid)
            c3.metric("المتبقي", total - paid)
            
            st.divider()
            st.subheader("📂 ملفاتك ودرجاتك")
            try:
                ws = sheet.worksheet(str(u['Code']))
                data = ws.get_all_records()
                st.dataframe(data, use_container_width=True)
            except:
                st.info("الملف قيد التجهيز")
                
            if st.button("خروج"):
                st.session_state['logged_in_student'] = None
                st.rerun()

    # ------------------------- بوابة المعلم (التعديل الجبار) -------------------------
    elif menu == "بوابة المعلم":
        # التحقق من الدخول
        if st.session_state['logged_in_teacher'] is None:
            st.header("👨‍🏫 بوابة المعلمين")
            t_code_in = st.text_input("كود المعلم")
            t_pass_in = st.text_input("كلمة المرور", type="password")
            
            if st.button("دخول المعلم"):
                df_t = get_data(sheet, "Teachers_Main")
                if not df_t.empty:
                    df_t['Code'] = df_t['Code'].astype(str)
                    df_t['Password'] = df_t['Password'].astype(str)
                    
                    teacher = df_t[(df_t['Code'] == t_code_in) & (df_t['Password'] == t_pass_in)]
                    if not teacher.empty:
                        st.session_state['logged_in_teacher'] = teacher.iloc[0].to_dict()
                        st.rerun()
                    else:
                        st.error("بيانات غير صحيحة")
        else:
            # المعلم مسجل دخول
            teacher_data = st.session_state['logged_in_teacher']
            t_code = str(teacher_data['Code'])
            st.title(f"أهلاً د/ {teacher_data['Name']}")
            st.caption(f"Code: {t_code}")
            
            st.divider()
            
            # 1. جلب المواد الخاصة بهذا المعلم فقط
            st.subheader("📚 موادي الدراسية")
            
            df_subjects = get_data(sheet, "Subjects_Data")
            
            if not df_subjects.empty and 'Teacher_Code' in df_subjects.columns:
                # فلترة المواد للكود ده بس
                df_subjects['Teacher_Code'] = df_subjects['Teacher_Code'].astype(str)
                my_subjects = df_subjects[df_subjects['Teacher_Code'] == t_code]
                
                if not my_subjects.empty:
                    # قائمة منسدلة لاختيار المادة
                    subject_list = my_subjects['Subject_Name'].tolist()
                    selected_subject = st.selectbox("اختر المادة للتحكم:", subject_list)
                    
                    # لما يختار مادة، نظهر تفاصيلها أو طلابها
                    st.info(f"أنت الآن تتحكم في مادة: **{selected_subject}**")
                    
                    # محاكاة لرصد الدرجات
                    with st.expander("رصد درجات طالب"):
                        stud_code_grade = st.text_input("كود الطالب")
                        grade_val = st.radio("النتيجة", ["ناجح", "راسب"])
                        if st.button("حفظ النتيجة"):
                            # هنا ممكن نكتب في شيت الطالب
                            try:
                                ws_s = sheet.worksheet(stud_code_grade)
                                ws_s.append_row(["نتيجة مادة", selected_subject, grade_val, str(datetime.now())])
                                st.success(f"تم رصد {grade_val} للطالب في {selected_subject}")
                            except:
                                st.error("تأكد من كود الطالب")
                else:
                    st.warning("لا توجد مواد مسندة إليك في الجدول (Subjects_Data). يرجى مراجعة الإدارة.")
            else:
                st.error("جدول المواد (Subjects_Data) غير موجود أو فارغ.")
                
            st.divider()
            if st.button("تسجيل خروج المعلم"):
                st.session_state['logged_in_teacher'] = None
                st.rerun()

    # ------------------------- البحث -------------------------
    elif menu == "البحث والاستعلام":
        st.header("🔍 استعلام إداري")
        q = st.text_input("بحث (الاسم أو الكود)")
        if q:
            df = get_data(sheet, "Students_Main")
            if not df.empty:
                df = df.astype(str)
                res = df[df['Code'].str.contains(q, case=False) | df['Name'].str.contains(q, case=False)]
                
                if not res.empty:
                    for i, r in res.iterrows():
                        with st.expander(f"{r['Name']} - {r['Code']}"):
                            st.write(f"الفرقة: {r['Year']}")
                            st.write(f"المدفوع: {r['Paid_Tuition']}")
                            st.write(f"الباسوورد: {r['Password']}")
                else:
                    st.warning("لا توجد نتائج")

if __name__ == '__main__':
    main()
