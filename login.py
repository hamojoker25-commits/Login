import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random
import string
from datetime import datetime

# --- إعدادات الصفحة ---
st.set_page_config(page_title="نظام إدارة المستخدمين", layout="centered")

# اسم ملف جوجل شيت
SHEET_NAME = "users_database"
MAIN_WORKSHEET_NAME = "All_Users_Data"

# --- الاتصال بجوجل شيت ---
def connect_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = st.secrets["gcp_service_account"]
            creds_json = dict(creds_dict)
            
            if "private_key" in creds_json:
                creds_json["private_key"] = creds_json["private_key"].replace("\\n", "\n")
            
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
            client = gspread.authorize(creds)
            sheet = client.open(SHEET_NAME)
            return sheet
        else:
            st.error("بيانات الدخول غير موجودة في Secrets.")
            return None
    except Exception as e:
        st.error(f"خطأ اتصال: {e}")
        return None

def init_sheet(sheet):
    try:
        worksheet = sheet.worksheet(MAIN_WORKSHEET_NAME)
        # التأكد من وجود عمود Link في الرئيسي احتياطياً
        headers = worksheet.row_values(1)
        if "Link" not in headers:
            worksheet.update_cell(1, len(headers)+1, "Link")
    except:
        worksheet = sheet.add_worksheet(title=MAIN_WORKSHEET_NAME, rows="1000", cols="20")
        worksheet.append_row(["User_Code", "First_Name", "Second_Name", "Email", "Password", "DOB", "Age", "Created_At", "Link"])
    return worksheet

# --- دوال المنطق ---

def calculate_age(birth_date):
    today = datetime.now().date()
    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    return age

def generate_user_code():
    letter = random.choice(string.ascii_uppercase)
    digits = random.sample(string.digits, 5)
    code = letter + "".join(digits)
    return code

def save_new_user(f_name, s_name, email, password, dob, age, user_link):
    sheet = connect_google_sheet()
    if not sheet: return None
    
    ws_main = init_sheet(sheet)
    
    try:
        existing_codes = ws_main.col_values(1)
    except:
        existing_codes = []
    
    while True:
        user_code = generate_user_code()
        if user_code not in existing_codes:
            break
            
    if not user_link:
        user_link = ""
    
    ws_main.append_row([user_code, f_name, s_name, email, password, str(dob), age, str(datetime.now()), user_link])
    
    # إنشاء الشيت الخاص فوراً
    try:
        try:
            sheet.worksheet(user_code)
        except:
            ws_user = sheet.add_worksheet(title=user_code, rows="100", cols="10")
            # هنا بنجهز العناوين في الشيت الخاص عشان يكون جاهز
            ws_user.append_row(["الموضوع", "ملاحظات", "التاريخ", "Link"]) 
    except:
        pass
        
    return user_code

def verify_login(user_code, password):
    sheet = connect_google_sheet()
    if not sheet: return None
    
    ws_main = init_sheet(sheet)
    data = ws_main.get_all_records()
    df = pd.DataFrame(data)
    
    if df.empty: return None

    df['User_Code'] = df['User_Code'].astype(str)
    df['Password'] = df['Password'].astype(str)
    
    user_row = df[(df['User_Code'] == str(user_code)) & (df['Password'] == str(password))]
    
    if not user_row.empty:
        return user_row.iloc[0]
    else:
        return None

# --- الواجهة ---

def main():
    st.title("بوابة المستخدمين 🌐")

    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        st.session_state['user_data'] = None

    if st.session_state['logged_in']:
        user = st.session_state['user_data']
        
        # 1. عرض ترحيب بسيط (Metrics)
        st.success(f"أهلاً بك: {user['First_Name']} {user['Second_Name']}")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("الكود", user['User_Code'])
        c2.metric("العمر", user['Age'])
        c3.caption(f"تاريخ الانضمام: {str(user['Created_At'])[:10]}")
        
        st.divider()
        
        # 2. عرض بيانات الشيت الخاص فقط (بدلاً من الرئيسي)
        st.subheader(f"📂 ملفك الشخصي ({user['User_Code']})")
        
        sheet = connect_google_sheet()
        if sheet:
            try:
                # جلب الشيت الخاص
                user_ws = sheet.worksheet(str(user['User_Code']))
                data = user_ws.get_all_records()
                
                if data:
                    df = pd.DataFrame(data)
                    
                    # --- الذكاء الاصطناعي لتصليح الروابط ---
                    column_config_settings = {}
                    
                    # بندور على أي عمود اسمه Link أو رابط عشان نحوله لزرار
                    for col_name in df.columns:
                        if "link" in col_name.lower() or "رابط" in col_name:
                            
                            # دالة صغيرة بتضيف https لو ناقصة
                            def make_clickable(val):
                                if not val or pd.isna(val) or str(val).strip() == "":
                                    return None
                                url = str(val).strip()
                                if not url.startswith('http://') and not url.startswith('https://'):
                                    return f"https://{url}"
                                return url
                            
                            # تطبيق التصليح على العمود
                            df[col_name] = df[col_name].apply(make_clickable)
                            
                            # إعدادات العرض (LinkColumn)
                            column_config_settings[col_name] = st.column_config.LinkColumn(
                                label=col_name,
                                display_text="🔗 فتح الرابط",
                                help="اضغط لفتح الرابط الخارجي"
                            )

                    # عرض الجدول النهائي
                    st.dataframe(
                        df,
                        use_container_width=True,
                        column_config=column_config_settings,
                        hide_index=True
                    )
                else:
                    st.info("ملفك الشخصي فارغ حالياً. يمكن للإدارة إضافة بيانات هنا.")
            except Exception as e:
                st.warning("جاري تجهيز ملفك الشخصي... (لم يتم العثور على الشيت الخاص)")
                # زر محاولة إنشاء الشيت لو مش موجود
                if st.button("إنشاء ملفي الآن"):
                    try:
                        ws_user = sheet.add_worksheet(title=str(user['User_Code']), rows="100", cols="10")
                        ws_user.append_row(["الموضوع", "ملاحظات", "التاريخ", "Link"])
                        st.success("تم الإنشاء! اعمل تحديث للصفحة.")
                    except:
                        st.error("موجود بالفعل أو خطأ في الصلاحيات.")
        
        st.divider()
        if st.button("تحديث البيانات 🔄"):
            st.rerun()

        if st.button("تسجيل الخروج", type="primary"):
            st.session_state['logged_in'] = False
            st.session_state['user_data'] = None
            st.rerun()
            
    else:
        # --- صفحة الدخول / التسجيل ---
        menu = ["تسجيل الدخول", "إنشاء حساب جديد"]
        choice = st.sidebar.selectbox("القائمة", menu)
        
        if choice == "إنشاء حساب جديد":
            st.header("تسجيل مستخدم جديد")
            with st.form("signup"):
                c1, c2 = st.columns(2)
                f = c1.text_input("الاسم الأول")
                s = c2.text_input("الاسم الثاني")
                e = st.text_input("البريد الإلكتروني")
                d = st.date_input("تاريخ الميلاد", min_value=datetime(1950,1,1))
                lnk = st.text_input("رابط (CV/ملف) - اختياري")
                p1 = st.text_input("كلمة المرور", type="password")
                p2 = st.text_input("تأكيد كلمة المرور", type="password")
                sub = st.form_submit_button("تسجيل")
                
                if sub:
                    if p1 == p2 and f and e:
                        age = calculate_age(d)
                        with st.spinner('جاري التسجيل...'):
                            code = save_new_user(f, s, e, p1, d, age, lnk)
                        if code:
                            st.balloons()
                            st.success(f"تم التسجيل بنجاح! كودك هو: {code}")
                            st.info("احتفظ بالكود للدخول.")
                    else:
                        st.error("تأكد من البيانات وتطابق كلمة المرور")

        elif choice == "تسجيل الدخول":
            st.header("تسجيل الدخول")
            with st.form("login"):
                c = st.text_input("الكود (مثال: A12345)")
                p = st.text_input("كلمة المرور", type="password")
                sub = st.form_submit_button("دخول")
                
                if sub:
                    with st.spinner('جاري التحقق...'):
                        u = verify_login(c, p)
                    if u is not None:
                        st.session_state['logged_in'] = True
                        st.session_state['user_data'] = u
                        st.rerun()
                    else:
                        st.error("كود الدخول أو كلمة المرور غير صحيحة")

if __name__ == '__main__':
    main()
