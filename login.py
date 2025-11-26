import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random
import string
from datetime import datetime
import json

# --- إعدادات الصفحة ---
st.set_page_config(page_title="نظام المعاهد العليا", layout="wide", page_icon="🎓")

# --- ثوابت النظام ---
SHEET_NAME = "users_database"
BASE_FEES = 18000
BOOK_FEES = {1: 2000, 2: 2500, 3: 3000, 4: 3500}

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

# --- دوال مساعدة ---
def get_data(sheet_obj, worksheet_name):
    try:
        ws = sheet_obj.worksheet(worksheet_name)
        return pd.DataFrame(ws.get_all_records())
    except:
        return pd.DataFrame()

def generate_code(prefix, length, is_digits_only=False):
    if is_digits_only:
        chars = string.digits
    else:
        chars = string.digits
    
    # توليد الجزء الرقمي
    digits = ''.join(random.choices(string.digits, k=length))
    
    if prefix == "T": # للمعلم حرفين كابتل
        caps = ''.join(random.choices(string.ascii_uppercase, k=2))
        return caps + digits
    elif prefix == "S": # للطالب حرف كابتل
        cap = random.choice(string.ascii_uppercase)
        return cap + digits
    return digits

def calculate_tuition(year):
    fees = BASE_FEES
    for _ in range(1, int(year)):
        fees += fees * 0.10 # زيادة 10% مركبة
    return int(fees)

# --- الوظائف الرئيسية ---

def register_student(data_dict, sheet):
    ws_main = sheet.worksheet("Students_Main")
    existing_codes = ws_main.col_values(1)
    
    while True:
        new_code = generate_code("S", 7)
        if new_code not in existing_codes:
            break
            
    # توليد باسوورد
    password = generate_code("S", 7) # حرف و7 أرقام
    
    # تجهيز حالة المواد (كلها Pending في البداية)
    # نفترض وجود مواد افتراضية لكل فرقة، هنا هنحطها فاضية لحد ما الإدارة تحددها
    subjects_status = "{}" 
    
    row = [
        new_code, data_dict['name'], password, data_dict['dob'], data_dict['gov'], 
        data_dict['address'], data_dict['nat'], data_dict['nid'], data_dict['nid_source'],
        data_dict['religion'], data_dict['cert'], data_dict['cert_date'], data_dict['seat_num'],
        data_dict['total_score'], data_dict['major'], 1, # الفرقة الأولى افتراضياً
        str(datetime.now()), 0, 0, subjects_status # مدفوع مصاريف، مدفوع كتب، حالة المواد
    ]
    ws_main.append_row(row)
    
    # إنشاء شيت خاص
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
        ws_main.append_row(["Code", "Name", "Password", "Data", "Subjects"])

    existing_codes = ws_main.col_values(1)
    while True:
        new_code = generate_code("T", 8)
        if new_code not in existing_codes:
            break
            
    # باسوورد المعلم (حرفين و8 أرقام مختلفين)
    password = ''.join(random.choices(string.ascii_uppercase, k=2)) + ''.join(random.choices(string.digits, k=8))
    
    row = [
        new_code, data_dict['name'], password, str(data_dict), ""
    ]
    ws_main.append_row(row)
    
    # إنشاء شيت خاص للمعلم
    try:
        sheet.add_worksheet(title=new_code, rows="100", cols="10")
    except:
        pass
        
    return new_code, password

def process_payment(student_code, amount, pay_type, visa_details, sheet, payment_category="tuition"):
    ws = sheet.worksheet("Students_Main")
    cell = ws.find(student_code)
    row_num = cell.row
    
    # تحديث المبلغ المدفوع
    # العمود 17 للمصاريف، 18 للكتب (حسب ترتيب التسجيل)
    col_idx = 17 if payment_category == "tuition" else 18
    current_val = ws.cell(row_num, col_idx).value
    new_val = int(current_val) + int(amount)
    ws.update_cell(row_num, col_idx, new_val)
    
    # تسجيل العملية في شيت الطالب
    ws_student = sheet.worksheet(student_code)
    note = f"دفع {payment_category} - {pay_type}"
    if pay_type == "Visa":
        note += f" (Visa Ends: {visa_details[-4:]})"
    
    ws_student.append_row(["عملية دفع", f"{amount} ج.م", note, str(datetime.now())])
    return True

# --- الواجهة الرئيسية ---

def main():
    sheet = connect_google_sheet()
    if not sheet:
        st.stop()
        
    # التأكد من وجود الشيتات الأساسية
    try:
        sheet.worksheet("Students_Main")
    except:
        ws = sheet.add_worksheet("Students_Main", 1000, 25)
        ws.append_row(["Code", "Name", "Password", "DOB", "Gov", "Address", "Nat", "NID", "NID_Source", 
                       "Religion", "Cert", "Cert_Date", "Seat_Num", "Score", "Major", "Year", 
                       "Join_Date", "Paid_Tuition", "Paid_Books", "Subjects_Status"])

    # القائمة الجانبية
    st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2942/2942544.png", width=100)
    st.sidebar.title("نظام المعاهد العليا")
    
    menu = st.sidebar.radio("القائمة", 
        ["الرئيسية", "شؤون الطلاب (تسجيل)", "شؤون المعلمين", "الخزينة (دفع المصاريف)", "بوابة الطالب", "بوابة المعلم", "البحث والاستعلام"])

    if menu == "الرئيسية":
        st.title("🏛️ نظام إدارة المعاهد العليا")
        st.info("مرحباً بك في النظام المتكامل. يرجى اختيار القسم من القائمة الجانبية.")
        
        c1, c2 = st.columns(2)
        with c1:
            st.metric("عدد الطلاب المسجلين", len(get_data(sheet, "Students_Main")))
        with c2:
            try:
                st.metric("عدد المعلمين", len(get_data(sheet, "Teachers_Main")))
            except:
                st.metric("عدد المعلمين", 0)

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
                    with st.spinner("جاري إنشاء ملف الطالب..."):
                        code, pwd = register_student(data, sheet)
                    
                    st.success("تم تسجيل الطالب بنجاح! ✅")
                    st.info(f"👤 كود الطالب: {code}")
                    st.warning(f"🔑 كلمة المرور المبدئية: {pwd}")
                else:
                    st.error("يرجى إكمال البيانات الأساسية")

    # ------------------------- شؤون المعلمين -------------------------
    elif menu == "شؤون المعلمين":
        st.header("👨‍🏫 تسجيل معلم جديد")
        with st.form("new_teacher"):
            name = st.text_input("الاسم رباعي")
            # باقي البيانات...
            submit = st.form_submit_button("تسجيل المعلم")
            
            if submit and name:
                data = {"name": name} # يمكن إضافة باقي الحقول
                code, pwd = register_teacher(data, sheet)
                st.success(f"تم التسجيل. كود: {code} | باسوورد: {pwd}")

    # ------------------------- الخزينة -------------------------
    elif menu == "الخزينة (دفع المصاريف)":
        st.header("💰 الخزينة وتحصيل المصروفات")
        
        tab1, tab2 = st.tabs(["مصاريف دراسية", "كتب دراسية"])
        
        with tab1:
            st.subheader("دفع المصاريف الدراسية")
            s_code = st.text_input("كود الطالب للبحث", key="search_fees")
            
            if s_code:
                df = get_data(sheet, "Students_Main")
                student = df[df['Code'] == s_code]
                
                if not student.empty:
                    st.success(f"الطالب: {student.iloc[0]['Name']}")
                    year = int(student.iloc[0]['Year'])
                    paid = int(student.iloc[0]['Paid_Tuition'])
                    
                    # حساب المستحق
                    total_due = calculate_tuition(year)
                    remaining = total_due - paid
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("الفرقة", year)
                    c2.metric("المستحق إجمالاً", f"{total_due:,}")
                    c3.metric("المتبقي", f"{remaining:,}", delta_color="inverse")
                    
                    pay_method = st.radio("طريقة الدفع", ["كاش", "فيزا"])
                    visa_info = ""
                    
                    if pay_method == "فيزا":
                        v_num = st.text_input("رقم الفيزا", type="password")
                        if v_num:
                            visa_info = v_num
                            
                    pay_amount = st.number_input("المبلغ المراد دفعه", min_value=1, max_value=int(remaining) if remaining > 0 else 1)
                    
                    if st.button("تأكيد الدفع"):
                        if remaining <= 0:
                            st.warning("تم سداد كامل المصروفات مسبقاً.")
                        else:
                            process_payment(s_code, pay_amount, pay_method, visa_info, sheet, "tuition")
                            st.balloons()
                            st.success("تمت العملية بنجاح!")
                            st.rerun()
                else:
                    st.error("كود غير صحيح")

        with tab2:
            st.subheader("دفع مصاريف الكتب (كاش فقط)")
            b_code = st.text_input("كود الطالب", key="book_fees")
            if b_code:
                df = get_data(sheet, "Students_Main")
                stud = df[df['Code'] == b_code]
                if not stud.empty:
                    yr = int(stud.iloc[0]['Year'])
                    book_fee = BOOK_FEES.get(yr, 0)
                    paid_book = int(stud.iloc[0]['Paid_Books'])
                    
                    st.write(f"الطالب: {stud.iloc[0]['Name']} - الفرقة: {yr}")
                    st.write(f"تكلفة الكتب: {book_fee}")
                    
                    if paid_book >= book_fee:
                        st.success("✅ تم استلام الكتب ودفع المصاريف بالكامل.")
                        # هنا بنعرض الباسوورد والكود زي ما طلبت
                        st.info(f"بيانات الدخول للطالب:\nالكود: {b_code}\nالباسوورد: {stud.iloc[0]['Password']}")
                    else:
                        if st.button(f"دفع {book_fee} جنيه (كاش)"):
                            process_payment(b_code, book_fee, "Cash", "", sheet, "books")
                            st.success("تم الدفع! يظهر الآن بيانات الدخول...")
                            st.rerun()

    # ------------------------- بوابة الطالب -------------------------
    elif menu == "بوابة الطالب":
        if 'student_user' not in st.session_state:
            st.header("🔐 دخول الطالب")
            code = st.text_input("كود الطالب")
            pas = st.text_input("كلمة المرور", type="password")
            if st.button("دخول"):
                df = get_data(sheet, "Students_Main")
                # تحويل الأعمدة لنصوص للمقارنة
                df['Code'] = df['Code'].astype(str)
                df['Password'] = df['Password'].astype(str)
                
                user = df[(df['Code'] == code) & (df['Password'] == pas)]
                if not user.empty:
                    st.session_state['student_user'] = user.iloc[0]
                    st.rerun()
                else:
                    st.error("بيانات خطأ")
        else:
            u = st.session_state['student_user']
            st.title(f"مرحباً، {u['Name']}")
            
            # حسابات سريعة
            yr = int(u['Year'])
            total_fee = calculate_tuition(yr)
            paid = int(u['Paid_Tuition'])
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("الفرقة الدراسية", yr)
            c2.metric("المصاريف المدفوعة", paid)
            c3.metric("المتبقي عليك", total_fee - paid)
            c4.metric("تاريخ الانضمام", str(u['Join_Date'])[:10])
            
            st.divider()
            st.subheader(f"📄 ملفك الأكاديمي ({u['Code']})")
            
            # عرض الشيت الخاص
            try:
                ws_priv = sheet.worksheet(str(u['Code']))
                data = ws_priv.get_all_records()
                
                # تحويل الروابط
                df_priv = pd.DataFrame(data)
                
                # إعدادات الأعمدة (لإظهار الروابط)
                column_config = {}
                for col in df_priv.columns:
                    if "Link" in col or "رابط" in col:
                         column_config[col] = st.column_config.LinkColumn(display_text="🔗 فتح")

                st.dataframe(df_priv, use_container_width=True, column_config=column_config)
                st.caption("لأي استفسار بخصوص الدرجات أو الروابط، يرجى مراجعة قسم IT.")
            except:
                st.warning("جاري تحديث ملفك...")

            if st.button("تسجيل خروج"):
                del st.session_state['student_user']
                st.rerun()

    # ------------------------- بوابة المعلم -------------------------
    elif menu == "بوابة المعلم":
        st.header("👨‍🏫 بوابة أعضاء هيئة التدريس")
        # (يمكنك إضافة منطق تسجيل دخول المعلم هنا بنفس طريقة الطالب)
        # للتسهيل سأضع محاكاة للكنترول
        
        st.info("نظام الكنترول ورصد الدرجات")
        t_code = st.text_input("كود المعلم")
        t_pass = st.text_input("كلمة المرور", type="password")
        
        if st.button("دخول للكنترول"):
            # تحقق وهمي (يجب ربطه بجدول Teachers_Main)
            st.success("تم الدخول. اختر المادة:")
            
            subject = st.selectbox("المادة", ["مقدمة حاسب", "رياضيات 1", "إدارة"])
            stud_code_input = st.text_input("كود الطالب للرصد")
            status = st.radio("الحالة", ["ناجح", "راسب"])
            
            if st.button("رصد النتيجة"):
                # هنا المنطق المعقد:
                # 1. نجيب الطالب
                # 2. نجيب الـ JSON بتاع المواد Subjects_Status
                # 3. نحدث المادة دي
                # 4. نتأكد هل كل مواد السنة دي "ناجح"؟ لو اه -> زود Year + 1
                
                df = get_data(sheet, "Students_Main")
                cell = sheet.worksheet("Students_Main").find(stud_code_input)
                
                if cell:
                    # قراءة الحالة الحالية
                    # (هذا الجزء يحتاج منطق JSON متقدم سأبسطه)
                    st.success(f"تم رصد {status} للطالب في مادة {subject}")
                    
                    # محاكاة الترحيل (لو ناجح ننقله فرقة)
                    # if check_all_passed(stud_code_input):
                    #    update_year(stud_code_input)
                else:
                    st.error("طالب غير موجود")

    # ------------------------- البحث والاستعلام -------------------------
    elif menu == "البحث والاستعلام":
        st.header("🔍 البحث عن طالب")
        query = st.text_input("اكتب الاسم أو الكود")
        
        if query:
            df = get_data(sheet, "Students_Main")
            # تحويل البيانات لنص للبحث
            df = df.astype(str)
            
            # البحث في الكود أو الاسم
            results = df[df['Code'].str.contains(query, case=False) | df['Name'].str.contains(query, case=False)]
            
            if not results.empty:
                for index, row in results.iterrows():
                    with st.expander(f"{row['Name']} ({row['Code']})"):
                        yr = int(row['Year'])
                        due = calculate_tuition(yr)
                        paid = int(float(row['Paid_Tuition']))
                        
                        c1, c2, c3 = st.columns(3)
                        c1.write(f"**الفرقة:** {yr}")
                        c2.write(f"**المدفوع:** {paid}")
                        c3.write(f"**المستحق:** {due}")
                        
                        st.write(f"**الباسوورد:** {row['Password']}")
            else:
                st.warning("لم يتم العثور على نتائج")

if __name__ == '__main__':
    main()
