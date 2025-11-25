import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random
import string
from datetime import datetime
import json

# --- إعدادات الصفحة ---
st.set_page_config(page_title="نظام إدارة المستخدمين", layout="centered")

# اسم ملف جوجل شيت (لازم يكون نفس الاسم اللي في الدرايف)
SHEET_NAME = "users_database"
MAIN_WORKSHEET_NAME = "All_Users_Data"

# --- الاتصال بجوجل شيت ---
def connect_google_sheet():
    # الصلاحيات المطلوبة
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    try:
        # قراءة المفتاح من Secrets بالطريقة الجديدة السهلة
        json_content = st.secrets["gcp_json"]
        creds_dict = json.loads(json_content)
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # فتح الملف
        sheet = client.open(SHEET_NAME)
        return sheet
    except Exception as e:
        st.error(f"خطأ في الاتصال بجوجل شيت: {e}")
        st.info("تأكد من وضع المفتاح بين علامات التنصيص الثلاثة في Secrets.")
        return None

def init_sheet(sheet):
    """التأكد من وجود الصفحة الرئيسية وتجهيز الأعمدة"""
    try:
        worksheet = sheet.worksheet(MAIN_WORKSHEET_NAME)
    except:
        # لو مش موجودة، ننشئها
        worksheet = sheet.add_worksheet(title=MAIN_WORKSHEET_NAME, rows="1000", cols="20")
        worksheet.append_row(["User_Code", "First_Name", "Second_Name", "Email", "Password", "DOB", "Age", "Created_At"])
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

def save_new_user(f_name, s_name, email, password, dob, age):
    sheet = connect_google_sheet()
    if not sheet: return None
    
    ws_main = init_sheet(sheet)
    
    # التأكد من عدم تكرار الكود (قراءة العمود الأول)
    try:
        existing_codes = ws_main.col_values(1)
    except:
        existing_codes = []
    
    while True:
        user_code = generate_user_code()
        if user_code not in existing_codes:
            break
    
    # 1. الحفظ في الصفحة الرئيسية
    ws_main.append_row([user_code, f_name, s_name, email, password, str(dob), age, str(datetime.now())])
    
    # 2. إنشاء صفحة (Tab) خاصة للمستخدم
    try:
        try:
            sheet.worksheet(user_code)
        except:
            ws_user = sheet.add_worksheet(title=user_code, rows="100", cols="10")
            ws_user.append_row(["بيانات خاصة بالمستخدم", "ملاحظات", "التاريخ"])
    except Exception as e:
        st.warning(f"ملاحظة: لم يتم إنشاء الشيت الفرعي: {e}")
        
    return user_code

def verify_login(user_code, password):
    sheet = connect_google_sheet()
    if not sheet: return None
    
    ws_main = init_sheet(sheet)
    data = ws_main.get_all_records()
    df = pd.DataFrame(data)
    
    if df.empty:
        return None

    df['User_Code'] = df['User_Code'].astype(str)
    df['Password'] = df['Password'].astype(str)
    
    user_row = df[(df['User_Code'] == str(user_code)) & (df['Password'] == str(password))]
    
    if not user_row.empty:
        return user_row.iloc[0]
    else:
        return None

# --- الواجهة ---

def main():
    st.title("نظام التسجيل (Google Sheets) 🌐")

    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        st.session_state['user_data'] = None

    if st.session_state['logged_in']:
        user = st.session_state['user_data']
        st.success(f"مرحباً بك، {user['First_Name']}!")
        
        col1, col2 = st.columns(2)
        col1.metric("كود المستخدم", user['User_Code'])
        col2.metric("العمر", user['Age'])
        
        st.divider()
        st.subheader("📋 بياناتك المسجلة")
        
        sheet = connect_google_sheet()
        if sheet:
            try:
                user_ws = sheet.worksheet(str(user['User_Code']))
                data = user_ws.get_all_records()
                if data:
                    st.dataframe(data)
                else:
                    st.info("لم تقم بإضافة أي بيانات خاصة بعد.")
            except:
                st.warning("لم يتم العثور على ورقة البيانات الخاصة بك.")
        
        if st.button("تسجيل الخروج"):
            st.session_state['logged_in'] = False
            st.session_state['user_data'] = None
            st.rerun()
            
    else:
        menu = ["تسجيل الدخول", "إنشاء حساب جديد"]
        choice = st.sidebar.selectbox("القائمة", menu)
        
        if choice == "إنشاء حساب جديد":
            st.header("تسجيل مستخدم جديد")
            with st.form("signup_form"):
                c1, c2 = st.columns(2)
                f_name = c1.text_input("الاسم الأول")
                s_name = c2.text_input("الاسم الثاني")
                email = st.text_input("البريد الإلكتروني")
                dob = st.date_input("تاريخ الميلاد", min_value=datetime(1950,1,1))
                p1 = st.text_input("كلمة المرور", type="password")
                p2 = st.text_input("تأكيد كلمة المرور", type="password")
                submitted = st.form_submit_button("إنشاء الحساب")
                
                if submitted:
                    if p1 != p2:
                        st.error("كلمات المرور غير متطابقة")
                    elif not f_name or not email or not p1:
                        st.error("يرجى ملء كافة البيانات المطلوبة")
                    else:
                        age = calculate_age(dob)
                        with st.spinner('جاري الاتصال بجوجل...'):
                            code = save_new_user(f_name, s_name, email, p1, dob, age)
                        
                        if code:
                            st.success("تم التسجيل بنجاح! ✅")
                            st.info(f"كود الدخول الخاص بك هو: {code}")
                            st.warning("يرجى حفظ الكود لاستخدامه في تسجيل الدخول.")

        elif choice == "تسجيل الدخول":
            st.header("تسجيل الدخول")
            with st.form("login_form"):
                code_input = st.text_input("كود الدخول")
                pass_input = st.text_input("كلمة المرور", type="password")
                submitted = st.form_submit_button("دخول")
                
                if submitted:
                    with st.spinner('جاري التحقق...'):
                        user_data = verify_login(code_input, pass_input)
                    
                    if user_data is not None:
                        st.session_state['logged_in'] = True
                        st.session_state['user_data'] = user_data
                        st.rerun()
                    else:
                        st.error("كود الدخول أو كلمة المرور غير صحيحة")

if __name__ == '__main__':
    main()
