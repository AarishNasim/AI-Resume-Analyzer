SKILLS=['python','flask','django','sql','mysql','sqlite','javascript','html','css','react','pandas','numpy','excel','statistics','machine learning','scikit-learn','nlp','git','rest api','java','c++','data analysis']
def extract_skills(text):
    t=text.lower(); return [s for s in SKILLS if s in t]
