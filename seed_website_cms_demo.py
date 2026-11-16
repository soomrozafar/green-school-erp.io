from app import create_app
from app.extensions import db
from app.models import User, WebsiteHeroSlide, WebsiteAcademicPage

app = create_app()
with app.app_context():
    u = User.query.filter_by(username='website_editor').first()
    if not u:
        u = User(username='website_editor', role='website_editor', is_active_user=True)
        u.set_password('Web@12345')
        db.session.add(u)
    else:
        u.role = 'website_editor'
        u.is_active_user = True

    if WebsiteHeroSlide.query.count() == 0:
        slides = [
            ('PUBLIC SCHOOL GADAP · KARACHI','Learning Today.<br><strong>Leading Tomorrow.</strong>','A modern learning community focused on strong academics, character, technology and opportunities for every student.','site/images/campus-1.png','Explore School','#about',1),
            ('SMART SCHOOL · DIGITAL CAMPUS','Connected Learning.<br><strong>For Every Student.</strong>','A secure digital school platform connecting students, staff, academics and school services.','site/images/campus-2.jpg','Explore Academics','#academics',2),
            ('EDUCATION · CHARACTER · COMMUNITY','Growing Confident.<br><strong>Young Minds.</strong>','Academic excellence supported by student life, wellbeing, leadership and community.','site/images/campus-3.jpg','Student Life','#student-life',3),
        ]
        for k,t,txt,img,bt,bu,o in slides:
            db.session.add(WebsiteHeroSlide(kicker=k,title=t,text=txt,image_path=img,button_text=bt,button_url=bu,sort_order=o,is_active=True))

    if WebsiteAcademicPage.query.count() == 0:
        data = [
            ('elementary','elementary-school','Elementary School','site/images/elementary.png','ACADEMICS · ELEMENTARY SCHOOL','A strong foundation for curious, confident and creative young learners.','Our Elementary pathway builds foundational literacy, numeracy, social development, creativity and a positive attitude toward learning.','Foundational literacy|Numeracy & problem solving|Play-based and hands-on learning|Creative expression|Confidence & character','English, Urdu, Mathematics, Science, Environmental Studies, Art, Computing and Physical Education.','Students learn through interactive classroom experiences, projects, reading, creative activities and collaborative learning.','Teacher guidance, differentiated classroom support, parent communication and enrichment activities.','English|Urdu|Mathematics|Science|Environmental Studies|Art|Computing|Physical Education','Public School Gadap Elementary School provides a balanced foundation in literacy, numeracy, inquiry, creativity, character and digital learning.'),
            ('junior','junior-school','Junior School','site/images/elementary.png','ACADEMICS · JUNIOR SCHOOL','An engaging stage where students explore ideas, strengthen core skills and discover their interests.','Junior School develops cognitive, social and physical skills through a broad curriculum that combines core academics with creativity, digital learning and co-curricular opportunities.','Core academic skills|Digital learning|Creativity & design thinking|Reading & communication|Sports & co-curricular growth','English, Urdu, Mathematics, Science, Geography, Environmental Studies, Computing, Digital Learning, Art, Music, Creativity, Global Studies and Physical Education.','Students participate in projects, presentations, reading challenges, competitions, arts, sports and collaborative learning.','Academic assistance, teacher mentoring, reading support and structured parent-school communication.','English|Urdu|Mathematics|Science|Geography|Environmental Studies|Computing|Digital Learning|Art|Music|Creativity|Global Studies|Physical Education','Junior School at Public School Gadap develops strong core academics together with creativity, digital skills, communication, teamwork and confidence.'),
            ('senior','senior-school','Senior School','site/images/campus-3.jpg','ACADEMICS · SENIOR SCHOOL','A rigorous and future-focused pathway preparing students for higher education, careers and responsible citizenship.','Senior School combines academic depth, examination preparation, digital learning, career guidance and a rich co-curricular experience.','Academic rigor|Examination readiness|STEM & digital learning|Career guidance|Leadership & co-curricular development','Core languages, Mathematics, sciences, computing, humanities, business and elective pathways according to the school programme.','Students engage in subject-focused learning, projects, competitions, leadership opportunities, examinations and career planning.','Academic assistance, counseling, subject selection guidance, examination preparation and student mentoring.','English|Urdu|Mathematics|Pakistan Studies|Islamiyat|Physics|Chemistry|Biology|Computer Science|Economics|Accounting|Business Studies|History|Literature','Senior School at Public School Gadap prepares learners for higher education and future careers through rigorous academics, examination readiness, guidance and leadership opportunities.'),
        ]
        faqs = {
            'elementary':'[{"question":"What is the focus of Elementary School?","answer":"The focus is to build strong academic foundations while developing curiosity, confidence, creativity and positive learning habits."},{"question":"Which subjects are taught?","answer":"Students study languages, mathematics, science, environmental studies, art, computing and physical education."}]',
            'junior':'[{"question":"What makes Junior School different?","answer":"It combines core subjects with creativity, digital learning, communication, co-curricular activities and age-appropriate project work."},{"question":"How are students supported?","answer":"Teachers monitor progress and provide academic guidance, reading support and enrichment opportunities."}]',
            'senior':'[{"question":"What is the Senior School focus?","answer":"The focus is academic depth, examination readiness, future planning, digital skills and leadership development."},{"question":"Is career guidance available?","answer":"The programme includes academic and career guidance to help students plan subjects and future study pathways."}]'
        }
        for typ,slug,title,img,k,intro,overview,hi,curr,exp,sup,subs,ans in data:
            db.session.add(WebsiteAcademicPage(page_type=typ,slug=slug,title=title,hero_image=img,hero_kicker=k,intro=intro,overview=overview,highlights=hi,curriculum=curr,student_experience=exp,support_programs=sup,subjects=subs,answer_summary=ans,faq_json=faqs[typ],seo_title=f'{title} | Public School Gadap',meta_description=ans,seo_keywords=f'{title}, Public School Gadap, Karachi school, academics, education',is_published=True))
    db.session.commit()
    print('Website CMS demo data ready.')
    print('Username: website_editor')
    print('Password: Web@12345')
