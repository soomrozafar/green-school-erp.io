from app import create_app
from app.extensions import db
from app.models import Student

app = create_app()

students_data = [
    {"admission_no": "ADM-2026-001", "first_name": "Ali", "last_name": "Khan", "father_name": "Ahmed Khan", "gender": "Male", "phone": "0300-1234567", "address": "Karachi"},
    {"admission_no": "ADM-2026-002", "first_name": "Ayesha", "last_name": "Ahmed", "father_name": "Tariq Ahmed", "gender": "Female", "phone": "0301-2345678", "address": "Lahore"},
    {"admission_no": "ADM-2026-003", "first_name": "Muhammad", "last_name": "Bilal", "father_name": "Akram Bilal", "gender": "Male", "phone": "0302-3456789", "address": "Islamabad"},
    {"admission_no": "ADM-2026-004", "first_name": "Fatima", "last_name": "Noor", "father_name": "Farooq Noor", "gender": "Female", "phone": "0303-4567890", "address": "Rawalpindi"},
    {"admission_no": "ADM-2026-005", "first_name": "Umar", "last_name": "Farooq", "father_name": "Saeed Farooq", "gender": "Male", "phone": "0304-5678901", "address": "Faisalabad"},
    {"admission_no": "ADM-2026-006", "first_name": "Zainab", "last_name": "Bibi", "father_name": "Ghulam Nabi", "gender": "Female", "phone": "0305-6789012", "address": "Multan"},
    {"admission_no": "ADM-2026-007", "first_name": "Hamza", "last_name": "Malik", "father_name": "Zubair Malik", "gender": "Male", "phone": "0306-7890123", "address": "Peshawar"},
    {"admission_no": "ADM-2026-008", "first_name": "Areeba", "last_name": "Tariq", "father_name": "Tariq Mehmood", "gender": "Female", "phone": "0307-8901234", "address": "Quetta"},
    {"admission_no": "ADM-2026-009", "first_name": "Saad", "last_name": "Rehan", "father_name": "Rehan Siddiqui", "gender": "Male", "phone": "0308-9012345", "address": "Sialkot"},
    {"admission_no": "ADM-2026-010", "first_name": "Hira", "last_name": "Nasir", "father_name": "Nasir Mehmood", "gender": "Female", "phone": "0309-0123456", "address": "Gujranwala"},
    {"admission_no": "ADM-2026-011", "first_name": "Usman", "last_name": "Ghani", "father_name": "Abdul Ghani", "gender": "Male", "phone": "0310-1122334", "address": "Hyderabad"},
    {"admission_no": "ADM-2026-012", "first_name": "Mehwish", "last_name": "Hayat", "father_name": "Hayat Ullah", "gender": "Female", "phone": "0311-2233445", "address": "Abbottabad"},
    {"admission_no": "ADM-2026-013", "first_name": "Danyal", "last_name": "Zafar", "father_name": "Zafar Iqbal", "gender": "Male", "phone": "0312-3344556", "address": "Bahawalpur"},
    {"admission_no": "ADM-2026-014", "first_name": "Sana", "last_name": "Javed", "father_name": "Javed Akhtar", "gender": "Female", "phone": "0313-4455667", "address": "Sukkur"},
    {"admission_no": "ADM-2026-015", "first_name": "Talha", "last_name": "Anjum", "father_name": "Anjum Shahzad", "gender": "Male", "phone": "0314-5566778", "address": "Sargodha"},
    {"admission_no": "ADM-2026-016", "first_name": "Nimra", "last_name": "Bucha", "father_name": "Iqbal Bucha", "gender": "Female", "phone": "0315-6677889", "address": "Gujrat"},
    {"admission_no": "ADM-2026-017", "first_name": "Zohaib", "last_name": "Hassan", "father_name": "Mehmood Hassan", "gender": "Male", "phone": "0316-7788990", "address": "Mardan"},
    {"admission_no": "ADM-2026-018", "first_name": "Khadija", "last_name": "Kubra", "father_name": "Riaz Ahmed", "gender": "Female", "phone": "0317-8899001", "address": "Kasur"},
    {"admission_no": "ADM-2026-019", "first_name": "Bilal", "last_name": "Ahmed", "father_name": "Bashir Ahmed", "gender": "Male", "phone": "0318-9900112", "address": "Rahim Yar Khan"},
    {"admission_no": "ADM-2026-020", "first_name": "Rida", "last_name": "Moiz", "father_name": "Moiz Uddin", "gender": "Female", "phone": "0319-0011223", "address": "Sahiwal"},
    {"admission_no": "ADM-2026-021", "first_name": "Fahad", "last_name": "Mustafa", "father_name": "Ghulam Mustafa", "gender": "Male", "phone": "0320-1112233", "address": "Okara"},
    {"admission_no": "ADM-2026-022", "first_name": "Mahira", "last_name": "Khan", "father_name": "Aslam Khan", "gender": "Female", "phone": "0321-2223344", "address": "Wah Cantt"},
    {"admission_no": "ADM-2026-023", "first_name": "Shehryar", "last_name": "Munawar", "father_name": "Munawar Ali", "gender": "Male", "phone": "0322-3334455", "address": "Dera Ghazi Khan"},
    {"admission_no": "ADM-2026-024", "first_name": "Yusra", "last_name": "Rizvi", "father_name": "Syed Rizvi", "gender": "Female", "phone": "0323-4445566", "address": "Nawabshah"},
    {"admission_no": "ADM-2026-025", "first_name": "Danish", "last_name": "Ali", "father_name": "Shokat Ali", "gender": "Male", "phone": "0324-5556677", "address": "Mingora"},
    {"admission_no": "ADM-2026-026", "first_name": "Anum", "last_name": "Fayyaz", "father_name": "Fayyaz Hussain", "gender": "Female", "phone": "0325-6667788", "address": "Chiniot"},
    {"admission_no": "ADM-2026-027", "first_name": "Haris", "last_name": "Rauf", "father_name": "Rauf Ahmed", "gender": "Male", "phone": "0326-7778899", "address": "Kamoke"},
    {"admission_no": "ADM-2026-028", "first_name": "Madiha", "last_name": "Imam", "father_name": "Imam Bakhsh", "gender": "Female", "phone": "0327-8889900", "address": "Hafizabad"},
    {"admission_no": "ADM-2026-029", "first_name": "Shoaib", "last_name": "Malik", "father_name": "Abdul Malik", "gender": "Male", "phone": "0328-9990011", "address": "Sadiqabad"},
    {"admission_no": "ADM-2026-030", "first_name": "Rabia", "last_name": "Anjum", "father_name": "Nazeer Anjum", "gender": "Female", "phone": "0329-0001122", "address": "Mirpurkhas"},
    {"admission_no": "ADM-2026-031", "first_name": "Ahsan", "last_name": "Raza", "father_name": "Ahmad Raza", "gender": "Male", "phone": "0330-1213141", "address": "Burewala"},
    {"admission_no": "ADM-2026-032", "first_name": "Sidra", "last_name": "Batool", "father_name": "Qasim Batool", "gender": "Female", "phone": "0331-2324252", "address": "Kohat"},
    {"admission_no": "ADM-2026-033", "first_name": "Waqas", "last_name": "Younus", "father_name": "Muhammad Younus", "gender": "Male", "phone": "0332-3435363", "address": "Khanewal"},
    {"admission_no": "ADM-2026-034", "first_name": "Aiman", "last_name": "Khan", "father_name": "Sultan Khan", "gender": "Female", "phone": "0333-4546474", "address": "Dadu"},
    {"admission_no": "ADM-2026-035", "first_name": "Junaid", "last_name": "Jamshed", "father_name": "Jamshed Ahmed", "gender": "Male", "phone": "0334-5657585", "address": "Muzaffargarh"},
    {"admission_no": "ADM-2026-036", "first_name": "Bushra", "last_name": "Ansari", "father_name": "Rafiq Ansari", "gender": "Female", "phone": "0335-6768696", "address": "Khanpur"},
    {"admission_no": "ADM-2026-037", "first_name": "Kashif", "last_name": "Ali", "father_name": "Manzoor Ali", "gender": "Male", "phone": "0336-7879808", "address": "Tando Adam"},
    {"admission_no": "ADM-2026-038", "first_name": "Uzma", "last_name": "Gilani", "father_name": "Syed Gilani", "gender": "Female", "phone": "0337-8980919", "address": "Khuzdar"},
    {"admission_no": "ADM-2026-039", "first_name": "Nabeel", "last_name": "Shaukat", "father_name": "Shaukat Ali", "gender": "Male", "phone": "0338-9091020", "address": "Shikarpur"},
    {"admission_no": "ADM-2026-040", "first_name": "Saira", "last_name": "Kazmi", "father_name": "Akhtar Kazmi", "gender": "Female", "phone": "0339-0102131", "address": "Jacobabad"},
    {"admission_no": "ADM-2026-041", "first_name": "Imran", "last_name": "Nazir", "father_name": "Nazir Ahmed", "gender": "Male", "phone": "0340-1314151", "address": "Muzaffarabad"},
    {"admission_no": "ADM-2026-042", "first_name": "Maria", "last_name": "Wasti", "father_name": "Raza Wasti", "gender": "Female", "phone": "0341-2425262", "address": "Mirpur"},
    {"admission_no": "ADM-2026-043", "first_name": "Zeeshan", "last_name": "Awan", "father_name": "Sikandar Awan", "gender": "Male", "phone": "0342-3536373", "address": "Gilgit"},
    {"admission_no": "ADM-2026-044", "first_name": "Sadia", "last_name": "Imam", "father_name": "Hussain Imam", "gender": "Female", "phone": "0343-4647484", "address": "Skardu"},
    {"admission_no": "ADM-2026-045", "first_name": "Farhan", "last_name": "Akhtar", "father_name": "Jan Akhtar", "gender": "Male", "phone": "0344-5758595", "address": "Turbat"},
    {"admission_no": "ADM-2026-046", "first_name": "Madiha", "last_name": "Shah", "father_name": "Pir Shah", "gender": "Female", "phone": "0345-6869706", "address": "Zhob"},
    {"admission_no": "ADM-2026-047", "first_name": "Asim", "last_name": "Jofa", "father_name": "Nawaz Jofa", "gender": "Male", "phone": "0346-7970817", "address": "Chaman"},
    {"admission_no": "ADM-2026-048", "first_name": "Kinza", "last_name": "Hashmi", "father_name": "Zubair Hashmi", "gender": "Female", "phone": "0347-8081928", "address": "Attock"},
    {"admission_no": "ADM-2026-049", "first_name": "Rehan", "last_name": "Sheikh", "father_name": "Akram Sheikh", "gender": "Male", "phone": "0348-9192039", "address": "Jhelum"},
    {"admission_no": "ADM-2026-050", "first_name": "Amna", "last_name": "Liaquat", "father_name": "Liaquat Ali", "gender": "Female", "phone": "0349-0203140", "address": "Sheikhupura"}
]

with app.app_context():
    count = 0
    for data in students_data:
        existing = Student.query.filter_by(admission_no=data["admission_no"]).first()
        if not existing:
            student = Student(**data)
            db.session.add(student)
            count += 1
    db.session.commit()
    print(f"Successfully added {count} new students to the database!")