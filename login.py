import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random
import string
from datetime import datetime
import time

# ---------------------------------------------------------
# 1. إعدادات النظام والتصميم
# ---------------------------------------------------------
st.set_page_config(page_title="نظام المعاهد العليا V4", layout="wide", page_icon="🏛️")

# اسم ملف جوجل شيت (يجب أن يكون موجوداً في الدرايف)
SHEET_NAME = "users_database"

# الثوابت المالية
BASE_TUITION = 18000  # مصاريف الفرقة الأولى
BOOK_FEES_MAP = {1: 2000, 2: 2500, 3: 3000, 4: 3500} # مصاريف الكتب

# --- تعريف هيكل البيانات (لضمان عدم حدوث أخطاء) ---
# هذه القوائم هي التي ستكون عناوين الأعمدة في جوجل شيت
HEADERS_STUDENT = [
    "Code", "Name", "Password", "Year", "Paid_Tuition", "Paid_Books", 
    "National_ID", "NID_Source", "Address", "Governorate", "Nationality", 
    "Religion", "DOB", "Phone", "Certificate", "Cert_Date", "Seat_Num", 
    "Total_Score", "Major", "Join_Date"
]

HEADERS_TEACHER = [
    "Code", "Name", "Password", "National_ID", "NID_Source", 
    "Phone", "Email", "Address", "Governorate", "Nationality", 
    "Religion", "DOB", "Join_Date"
]

HEADERS_SUBJECTS = ["Subject_Name", "Teacher_Code", "Teacher_Name", "Year_Level"]

# ---------------------------------------------------------
# 2. إدارة الاتصال والبيانات (Backend)
# ---------------------------------------------------------

@st.cache_resource
def get_gspread_client():
    """الاتصال بجوجل درايف مرة واحدة"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            # تصحيح مفتاح التشفير
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            return client
        else:
            st.error("❌ لم يتم العثور على أسرار الاتصال (Secrets).")
            return None
    except Exception as e:
        st.error(f"خطأ في الاتصال: {e}")
        return None

def ensure_sheet_structure(client):
    """
    الدالة السحرية: تتأكد من وجود الصفحات والعناوين الصحيحة
    وتصلح أي خطأ (Duplicate Headers) تلقائياً
    """
    if not client: return False
    
    try:
        sheet = client.open(SHEET_NAME)
    except:
        st.error(f"الملف {SHEET_NAME} غير موجود في جوجل درايف!")
        return False

    # قائمة الشيتات المطلوبة وهيدراتها
    required_sheets = {
        "Students_Main": HEADERS_STUDENT,
        "Teachers_Main": HEADERS_TEACHER,
        "Subjects_Data": HEADERS_SUBJECTS
    }

    for ws_name, headers in required_sheets.items():
        try:
            ws = sheet.worksheet(ws_name)
            # التحقق من الصف الأول
            current_headers = ws.row_values(1)
            
            # إذا كان فارغاً أو غير مطابق أو به مشاكل -> أعد بناءه
            if not current_headers or current_headers != headers:
                # مسح المحتوى القديم للصف الأول وكتابة الجديد
                ws.resize(cols=len(headers))
                # نستخدم range لتحديث الصف الأول فقط
                cell_list = ws.range(1, 1, 1, len(headers))
                for i, cell in enumerate(cell_list):
                    cell.value = headers[i]
                ws.update_cells(cell_list)
        except:
            # لو الشيت مش موجود ننشئه
            ws = sheet.add_worksheet(ws_name, 1000, len(headers))
            ws.append_row(headers)
            
    return True

def get_data_frame(ws_name):
    """جلب البيانات كـ DataFrame"""
    client = get_gspread_client()
    if not client: return pd.DataFrame()
    sheet = client.open(SHEET_NAME)
    try:
        ws = sheet.worksheet(ws_name)
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

# ---------------------------------------------------------
# 3. دوال المنطق (Logic Functions)
# ---------------------------------------------------------

def generate_code(role):
    """توليد كود عشوائي قوي"""
    digits = ''.join(random.choices(string.digits, k=7))
    if role == "Teacher":
        # حرفين كابتل + 8 أرقام
        prefix = ''.join(random.choices(string.ascii_uppercase, k=2))
        return f"{prefix}{digits}8"
    else:
        # حرف كابتل + 7 أرقام
        prefix = random.choice(string.ascii_uppercase)
        return f"{prefix}{digits}"

def calculate_fees(current_year):
    """حساب المصاريف بنظام الفائدة المركبة 10%"""
    fees = BASE_TUITION
    try:
        y = int(current_year)
    except:
        y = 1
        
    for _ in range(1, y):
        fees = fees + (fees * 0.10) # زيادة 10%
    return int(fees)

def register_logic(role, data):
    client = get_gspread_client()
    sheet = client.open(SHEET_NAME)
    
    if role == "Teacher":
        ws_name = "Teachers_Main"
        headers = HEADERS_TEACHER
        code_prefix = "Teacher"
    else:
        ws_name = "Students_Main"
        headers = HEADERS_STUDENT
        code_prefix = "Student"

    ws = sheet.worksheet(ws_name)
    
    # توليد كود غير مكرر
    try: existing_codes = ws.col_values(1)
    except: existing_codes = []
    
    while True:
        new_code = generate_code(role)
        if new_code not in existing_codes:
            break
    
    # توليد باسوورد
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    
    # تجهيز الصف بنفس ترتيب الهيدرز (مهم جداً)
    row_data = []
    
    # إضافة الكود والباسوورد أولاً
    data["Code"] = new_code
    data["Password"] = password
    data["Join_Date"] = str(datetime.now())
    
    if role == "Student":
        data["Year"] = 1
        data["Paid_Tuition"] = 0
        data["Paid_Books"] = 0
    
    # تعبئة القائمة بالترتيب الصحيح
    for field in headers:
        row_data.append(data.get(field, ""))
        
    ws.append_row(row_data)
    
    # إنشاء الشيت الخاص
    try:
        try:
            sheet.worksheet(new_code)
        except:
            ws_p = sheet.add_worksheet(title=new_code, rows="100", cols="10")
            ws_p.append_row(["النوع", "التفاصيل", "التاريخ", "Link"])
            ws_p.append_row(["تنبيه", "هذا الملف خاص بالطالب/المعلم", str(datetime.now()), ""])
    except:
        pass
        
    return new_code, password

# ---------------------------------------------------------
# 4. واجهات المستخدم (Frontend)
# ---------------------------------------------------------

def admin_portal():
    st.title("🛠️ لوحة الإدارة العامة (Admin Control)")
    st.info("مرحباً بمدير النظام. يرجى اختيار القسم.")
    
    tab1, tab2, tab3, tab4 = st.tabs(["تسجيل الطلاب", "تسجيل المعلمين", "الخزينة", "توزيع المواد"])
    
    # --- 1. تسجيل الطلاب (كامل) ---
    with tab1:
        st.subheader("📝 تسجيل طالب جديد")
        with st.form("reg_student_form"):
            col1, col2 = st.columns(2)
            name = col1.text_input("الاسم رباعي")
            nid = col2.text_input("الرقم القومي")
            
            col3, col4 = st.columns(2)
            nid_src = col3.text_input("جهة الإصدار")
            dob = col4.date_input("تاريخ الميلاد", min_value=datetime(1990,1,1))
            
            col5, col6 = st.columns(2)
            nat = col5.text_input("الجنسية", "مصر")
            rel = col6.selectbox("الديانة", ["مسلم", "مسيحي", "أخرى"])
            
            col7, col8 = st.columns(2)
            gov = col7.text_input("المحافظة")
            addr = col8.text_input("العنوان بالتفصيل")
            
            st.markdown("---")
            st.caption("بيانات المؤهل")
            c1, c2, c3 = st.columns(3)
            cert = c1.text_input("الشهادة (ثانوية/دبلوم)")
            cert_date = c2.date_input("تاريخ الشهادة")
            seat = c3.text_input("رقم الجلوس")
            
            c4, c5 = st.columns(2)
            score = c4.number_input("المجموع", min_value=0.0)
            major = c5.selectbox("التخصص", ["نظم معلومات", "إدارة أعمال", "محاسبة"])
            
            phone = st.text_input("رقم الهاتف")
            
            submit = st.form_submit_button("حفظ بيانات الطالب")
            
            if submit and name and nid:
                with st.spinner("جاري الحفظ في قاعدة البيانات..."):
                    data_pack = {
                        "Name": name, "National_ID": nid, "NID_Source": nid_src,
                        "DOB": str(dob), "Nationality": nat, "Religion": rel,
                        "Governorate": gov, "Address": addr, "Certificate": cert,
                        "Cert_Date": str(cert_date), "Seat_Num": seat,
                        "Total_Score": score, "Major": major, "Phone": phone
                    }
                    code, pwd = register_logic("Student", data_pack)
                
                st.success("تم التسجيل بنجاح! ✅")
                st.metric("كود الطالب", code)
                st.code(pwd, language="text") # عرض الباسوورد
                st.warning("يرجى إعطاء هذه البيانات للطالب فوراً.")

    # --- 2. تسجيل المعلمين (كامل) ---
    with tab2:
        st.subheader("👨‍🏫 تسجيل عضو هيئة تدريس")
        with st.form("reg_teacher_form"):
            t1, t2 = st.columns(2)
            tn = t1.text_input("الاسم رباعي")
            tnid = t2.text_input("الرقم القومي")
            
            t3, t4 = st.columns(2)
            tnsrc = t3.text_input("جهة الإصدار")
            tdob = t4.date_input("تاريخ الميلاد", min_value=datetime(1960,1,1))
            
            t5, t6 = st.columns(2)
            tnat = t5.text_input("الجنسية", "مصر")
            trel = t6.selectbox("الديانة", ["مسلم", "مسيحي"])
            
            t7, t8 = st.columns(2)
            tgov = t7.text_input("المحافظة")
            taddr = t8.text_input("العنوان")
            
            t9, t10 = st.columns(2)
            temail = t9.text_input("البريد الإلكتروني")
            tphone = t10.text_input("رقم الهاتف")
            
            tsub = st.form_submit_button("حفظ بيانات المعلم")
            
            if tsub and tn:
                with st.spinner("جاري إنشاء حساب المعلم..."):
                    data_pack = {
                        "Name": tn, "National_ID": tnid, "NID_Source": tnsrc,
                        "DOB": str(tdob), "Nationality": tnat, "Religion": trel,
                        "Governorate": tgov, "Address": taddr, "Email": temail,
                        "Phone": tphone
                    }
                    code, pwd = register_logic("Teacher", data_pack)
                st.success("تم إنشاء الحساب! 🚀")
                st.info(f"كود المعلم: {code} | الباسوورد: {pwd}")

    # --- 3. الخزينة (الذكية) ---
    with tab3:
        st.subheader("💰 الخزينة والمدفوعات")
        
        search_code = st.text_input("بحث بكود الطالب", key="pay_search")
        if st.button("بحث عن الطالب"):
            df = get_data_frame("Students_Main")
            if not df.empty:
                df['Code'] = df['Code'].astype(str)
                res = df[df['Code'] == str(search_code).strip()]
                if not res.empty:
                    st.session_state['active_pay_student'] = res.iloc[0].to_dict()
                else:
                    st.error("طالب غير موجود")
        
        if 'active_pay_student' in st.session_state:
            stu = st.session_state['active_pay_student']
            st.markdown(f"**الطالب:** {stu['Name']} | **الفرقة:** {stu['Year']}")
            
            # حسابات
            try: yr = int(stu['Year'])
            except: yr = 1
            
            # المصاريف الدراسية
            tuition_total = calculate_fees(yr)
            tuition_paid = int(str(stu['Paid_Tuition']).replace(',','')) if str(stu['Paid_Tuition']).replace(',','').isdigit() else 0
            tuition_rem = tuition_total - tuition_paid
            
            # مصاريف الكتب
            book_total = BOOK_FEES_MAP.get(yr, 2000)
            book_paid = int(str(stu['Paid_Books']).replace(',','')) if str(stu['Paid_Books']).replace(',','').isdigit() else 0
            book_rem = book_total - book_paid
            
            pay_type = st.radio("نوع السداد", ["مصاريف دراسية", "كتب دراسية"], horizontal=True)
            
            c1, c2, c3 = st.columns(3)
            
            if pay_type == "مصاريف دراسية":
                target_rem = tuition_rem
                col_idx_update = 5 # Paid_Tuition index (1-based in sheet is 5)
                c1.metric("المستحق", f"{tuition_total:,}")
                c2.metric("المدفوع", f"{tuition_paid:,}")
                c3.metric("المتبقي", f"{tuition_rem:,}", delta_color="inverse")
            else:
                target_rem = book_rem
                col_idx_update = 6 # Paid_Books index (1-based in sheet is 6)
                c1.metric("سعر الكتب", f"{book_total:,}")
                c2.metric("المدفوع", f"{book_paid:,}")
                c3.metric("المتبقي", f"{book_rem:,}", delta_color="inverse")

            # طريقة الدفع
            method = st.radio("طريقة الدفع", ["كاش", "فيزا"])
            visa_last4 = ""
            if method == "فيزا":
                c_num = st.text_input("رقم الفيزا", type="password")
                c_cvv = st.text_input("الرقم السري (CVV)", type="password")
                if c_num: visa_last4 = c_num[-4:]
            
            amount = st.number_input("المبلغ المدفوع", min_value=0, max_value=target_rem if target_rem > 0 else 0)
            
            if st.button("تأكيد العملية"):
                if amount > 0:
                    client = get_gspread_client()
                    sheet = client.open(SHEET_NAME)
                    ws = sheet.worksheet("Students_Main")
                    cell = ws.find(str(stu['Code']))
                    
                    # تحديث الرصيد (إضافة المبلغ الجديد للقديم)
                    old_val = tuition_paid if pay_type == "مصاريف دراسية" else book_paid
                    ws.update_cell(cell.row, col_idx_update, old_val + amount)
                    
                    # تسجيل الإيصال في شيت الطالب
                    note = f"دفع {pay_type} ({method})"
                    if visa_last4: note += f" - Visa **{visa_last4}"
                    try:
                        sheet.worksheet(str(stu['Code'])).append_row([pay_type, f"{amount} ج.م", note, str(datetime.now())])
                    except: pass
                    
                    st.balloons()
                    st.success("تمت العملية بنجاح!")
                    del st.session_state['active_pay_student'] # مسح البيانات عشان التحديث
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning("المبلغ يجب أن يكون أكبر من صفر")

    # --- 4. توزيع المواد ---
    with tab4:
        st.subheader("📚 إسناد المواد للمعلمين")
        
        teachers_df = get_data_frame("Teachers_Main")
        if not teachers_df.empty:
            # قائمة المعلمين
            t_options = [f"{r['Name']} | {r['Code']}" for i, r in teachers_df.iterrows()]
            selected_t = st.selectbox("اختار المعلم", t_options)
            
            if selected_t:
                t_code = selected_t.split(" | ")[1]
                t_name = selected_t.split(" | ")[0]
                
                sub_name = st.text_input("اسم المادة")
                y_lvl = st.selectbox("الفرقة الدراسية", [1, 2, 3, 4])
                
                if st.button("إضافة المادة"):
                    client = get_gspread_client()
                    sheet = client.open(SHEET_NAME)
                    ws_sub = sheet.worksheet("Subjects_Data")
                    ws_sub.append_row([sub_name, t_code, t_name, y_lvl])
                    st.success(f"تم إسناد مادة {sub_name} للمعلم {t_name}")

def teacher_portal():
    user = st.session_state['user_info']
    st.title(f"👨‍🏫 بوابة المعلم: {user['Name']}")
    st.caption(f"Code: {user['Code']}")
    
    st.divider()
    st.subheader("📚 المواد المسندة إليك")
    
    df_sub = get_data_frame("Subjects_Data")
    if not df_sub.empty:
        # تحويل العمود لنص للبحث
        df_sub['Teacher_Code'] = df_sub['Teacher_Code'].astype(str)
        my_subs = df_sub[df_sub['Teacher_Code'] == str(user['Code'])]
        
        if not my_subs.empty:
            for idx, row in my_subs.iterrows():
                with st.expander(f"📘 {row['Subject_Name']} (الفرقة {row['Year_Level']})"):
                    st.write("أدوات المعلم:")
                    
                    col1, col2 = st.columns([3, 1])
                    s_code_search = col1.text_input("كود الطالب لرصد الدرجة", key=f"src_{idx}")
                    
                    status = st.radio("حالة الطالب", ["ناجح", "راسب"], key=f"st_{idx}", horizontal=True)
                    
                    if st.button("رصد النتيجة", key=f"btn_{idx}"):
                        if s_code_search:
                            # البحث عن الطالب والتسجيل في شيته
                            client = get_gspread_client()
                            sheet = client.open(SHEET_NAME)
                            try:
                                # نتأكد إن الطالب موجود
                                ws_main = sheet.worksheet("Students_Main")
                                if ws_main.find(s_code_search):
                                    # نسجل في شيت الطالب
                                    try:
                                        ws_s = sheet.worksheet(s_code_search)
                                        ws_s.append_row([f"نتيجة: {row['Subject_Name']}", status, str(datetime.now()), ""])
                                        st.success(f"تم رصد {status} للطالب.")
                                    except:
                                        st.warning("ملف الطالب غير مفعل، يرجى التواصل مع الإدارة.")
                                else:
                                    st.error("كود الطالب غير صحيح")
                            except:
                                st.error("خطأ في قاعدة البيانات")
        else:
            st.info("لا توجد مواد مسجلة لك حالياً.")
    
    st.divider()
    if st.button("خروج"):
        st.session_state['role'] = None
        st.rerun()

def student_portal():
    user = st.session_state['user_info']
    st.title(f"🎓 بوابة الطالب: {user['Name']}")
    
    # تفاصيل مالية ودراسية
    try: yr = int(user['Year'])
    except: yr = 1
    
    fees = calculate_fees(yr)
    paid = int(str(user['Paid_Tuition']).replace(',','')) if str(user['Paid_Tuition']).replace(',','').isdigit() else 0
    
    col1, col2, col3 = st.columns(3)
    col1.metric("الفرقة الدراسية", yr)
    col2.metric("المصاريف الدراسية", f"{fees:,}")
    col3.metric("المدفوع", f"{paid:,}")
    
    st.divider()
    st.subheader("📂 ملفك الأكاديمي")
    
    client = get_gspread_client()
    try:
        sheet = client.open(SHEET_NAME)
        ws = sheet.worksheet(str(user['Code']))
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        # عرض الجدول مع تحويل الروابط
        st.dataframe(
            df,
            column_config={
                "Link": st.column_config.LinkColumn("رابط", display_text="🔗 فتح"),
                "التاريخ": st.column_config.DatetimeColumn("التاريخ", format="D MMM YYYY, h:mm a")
            },
            use_container_width=True
        )
    except:
        st.info("لم يتم العثور على سجلات.")
        
    st.divider()
    if st.button("تسجيل الخروج"):
        st.session_state['role'] = None
        st.rerun()

# ---------------------------------------------------------
# 5. الصفحة الرئيسية (Main Entry)
# ---------------------------------------------------------

def main():
    # التأكد من هيكل البيانات قبل أي شيء
    client = get_gspread_client()
    if client:
        ensure_sheet_structure(client)
    
    # التوجيه حسب الصلاحية
    if 'role' not in st.session_state: st.session_state['role'] = None
    
    if st.session_state['role'] == "Admin":
        admin_portal()
    elif st.session_state['role'] == "Teacher":
        teacher_portal()
    elif st.session_state['role'] == "Student":
        student_portal()
    else:
        # شاشة الدخول الرئيسية
        st.title("🏛️ نظام إدارة المعاهد العليا")
        
        tab_s, tab_t, tab_a = st.tabs(["دخول الطلاب", "دخول المعلمين", "الإدارة"])
        
        with tab_s:
            with st.form("ls"):
                c = st.text_input("كود الطالب")
                p = st.text_input("كلمة المرور", type="password")
                if st.form_submit_button("دخول"):
                    df = get_data_frame("Students_Main")
                    if not df.empty:
                        df['Code'] = df['Code'].astype(str).str.strip()
                        df['Password'] = df['Password'].astype(str).str.strip()
                        u = df[(df['Code'] == str(c).strip()) & (df['Password'] == str(p).strip())]
                        if not u.empty:
                            st.session_state['role'] = "Student"
                            st.session_state['user_info'] = u.iloc[0].to_dict()
                            st.rerun()
                        else: st.error("بيانات خاطئة")
                    else: st.error("لا توجد بيانات")

        with tab_t:
            with st.form("lt"):
                c = st.text_input("كود المعلم")
                p = st.text_input("كلمة المرور", type="password")
                if st.form_submit_button("دخول"):
                    df = get_data_frame("Teachers_Main")
                    if not df.empty:
                        df['Code'] = df['Code'].astype(str).str.strip()
                        df['Password'] = df['Password'].astype(str).str.strip()
                        u = df[(df['Code'] == str(c).strip()) & (df['Password'] == str(p).strip())]
                        if not u.empty:
                            st.session_state['role'] = "Teacher"
                            st.session_state['user_info'] = u.iloc[0].to_dict()
                            st.rerun()
                        else: st.error("بيانات خاطئة")
        
        with tab_a:
            with st.form("la"):
                u = st.text_input("المستخدم")
                p = st.text_input("كلمة المرور", type="password")
                if st.form_submit_button("دخول"):
                    # باسوورد الإدارة الثابت
                    if u == "admin" and p == "admin123":
                        st.session_state['role'] = "Admin"
                        st.rerun()
                    else:
                        st.error("بيانات غير صحيحة")

if __name__ == '__main__':
    main()
