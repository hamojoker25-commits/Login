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
            st.error("لم يتم العثور على بيانات الدخول في Secrets.")
            return None
    except Exception as e:
        st.error(f"حدث خطأ في الاتصال بجوجل: {e}")
        return None

def init_sheet(sheet):
    try:
        worksheet = sheet.worksheet(MAIN_WORKSHEET_NAME)
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
            
    # معالجة الرابط لو فاضي عشان ميعملش مشاكل
    if not user_link:
        user_link = ""
    
    ws_main.append_row([user_code, f_name, s_name, email, password, str(dob), age, str(datetime.now()), user_link])
    
    try:
        try:
            sheet.worksheet(user_code)
        except:
            ws_user = sheet.add_worksheet(title=user_code, rows="100", cols="10")
            ws_user.append_row(["بيانات خاصة بالمستخدم", "ملاحظات", "التاريخ"])
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

    # تحويل البيانات لنصوص لتجنب الأخطاء
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
        
        # تحويل بيانات المستخدم لـ DataFrame
        my_info = pd.DataFrame([user])
        
        # --- التصليح هنا: التأكد من وجود عمود الرابط وتحويله لنص ---
        if "Link" not in my_info.columns:
            my_info["Link"] = "" # لو مش موجود نخليه فاضي
        
        # تحويل العمود لنص إجباري عشان منع الخطأ TypeError
        my_info["Link"] = my_info["Link"].astype(str)
        
        # لو الخانة فيها "nan" (يعني فاضية بلغة الكمبيوتر) نحولها لـ None عشان تظهر فاضية وماتعملش Error
        my_info["Link"] = my_info["Link"].replace('nan', None)
        my_info["Link"] = my_info["Link"].replace('', None)

        st.dataframe(
            my_info,
            column_config={
                "Link": st.column_config.LinkColumn(
                    "رابط الملف",
                    display_text="🔗 فتح الرابط"
                ),
                "Password": st.column_config.TextColumn("كلمة المرور", type="default")
            },
            hide_index=True
        )
        
        st.divider()
        st.subheader("📂 ملفاتك الخاصة")
        sheet = connect_google_sheet()
        if sheet:
            try:
                user_ws = sheet.worksheet(str(user['User_Code']))
                data = user_ws.get_all_records()
                if data:
                    st.dataframe(data)
                else:
                    st.info("لا توجد بيانات إضافية.")
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
            with st.form("signup"):
                c1, c2 = st.columns(2)
                f = c1.text_input("الاسم الأول")
                s = c2.text_input("الاسم الثاني")
                e = st.text_input("البريد الإلكتروني")
                d = st.date_input("تاريخ الميلاد", min_value=datetime(1950,1,1))
                
                lnk = st.text_input("رابط (CV أو ملف) - اختياري")
                
                p1 = st.text_input("كلمة المرور", type="password")
                p2 = st.text_input("تأكيد كلمة المرور", type="password")
                sub = st.form_submit_button("تسجيل")
                
                if sub:
                    if p1 == p2 and f and e:
                        age = calculate_age(d)
                        with st.spinner('جاري التسجيل...'):
                            code = save_new_user(f, s, e, p1, d, age, lnk)
                        if code:
                            st.success(f"تم! كودك: {code}")
                    else:
                        st.error("تأكد من البيانات")

        elif choice == "تسجيل الدخول":
            with st.form("login"):
                c = st.text_input("الكود")
                p = st.text_input("الباسوورد", type="password")
                sub = st.form_submit_button("دخول")
                
                if sub:
                    with st.spinner('جاري الدخول...'):
                        u = verify_login(c, p)
                    if u is not None:
                        st.session_state['logged_in'] = True
                        st.session_state['user_data'] = u
                        st.rerun()
                    else:
                        st.error("بيانات خطأ")

if __name__ == '__main__':
    main()
