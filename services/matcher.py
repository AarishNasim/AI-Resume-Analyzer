def match_jobs(resume_text,jobs):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    from services.skill_extractor import extract_skills
    resume_skills=set(extract_skills(resume_text))
    docs=[resume_text] + [j['description']+' '+j['required_skills'] for j in jobs]
    sims=cosine_similarity(TfidfVectorizer(stop_words='english').fit_transform(docs))[0][1:]
    out=[]
    for j,sim in zip(jobs,sims):
        req=[x.strip().lower() for x in j['required_skills'].split(',')]
        matched=[x for x in req if x in resume_skills]
        skill_score=(len(matched)/len(req)*100) if req else 0
        score=round(0.7*skill_score+0.3*float(sim*100),1)
        out.append({'id':j['id'],'title':j['title'],'company':j['company'],'location':j['location'],'required_skills':j['required_skills'],'matched':matched,'score':score})
    return sorted(out,key=lambda x:x['score'],reverse=True)
