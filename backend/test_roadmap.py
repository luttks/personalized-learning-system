import asyncio
from app.services.exam_service import run_full_exam_pipeline, generate_learning_roadmap, crawl_resources_per_phase, get_ai_recommendation_groq, ocr_and_parse
from app.core.config import settings

async def test_roadmap():
    print('Reading file...')
    with open(r'd:\TTTN\personalized-learning-system\personalized-learning-system\test\giao_trinh.pdf', 'rb') as f:
        file_bytes = f.read()
    
    print('Running OCR and parse...')
    parsed = await ocr_and_parse(file_bytes, 'giao_trinh.pdf', settings.gemini_api_keys)
    print(f'Found {parsed.get("question_count", 0)} questions')
    
    print('Generating AI recommendation...')
    questions = parsed.get("questions", [])
    raw_markdown = parsed.get("raw_markdown", "")
    ai_rec = await get_ai_recommendation_groq(
        questions=questions,
        raw_markdown=raw_markdown,
        exam_score=6.0,
        exam_max_score=10.0,
        mode="onboarding",
        groq_api_keys=settings.llm_api_keys,
        model=settings.llm_model,
        selected_goal="Nắm vững kiến thức"
    )
    
    print('Generating Roadmap...')
    roadmap = await generate_learning_roadmap(
        subject="Lịch sử Đảng",
        weak_topics=["Chương 1", "Chương 2"],
        selected_goal="Nắm vững kiến thức",
        score_ratio=0.6,
        minutes_per_day=60,
        gemini_api_keys=settings.gemini_api_keys,
        llm_api_keys=settings.llm_api_keys,
        llm_base_url=settings.llm_base_url,
        llm_model=settings.llm_model
    )
    
    print('Roadmap created:', roadmap.get("overview", ""))
    print('Phases count:', len(roadmap.get("phases", [])))
    
    if roadmap.get("phases"):
        print('Crawling per phase...')
        resources = await crawl_resources_per_phase(roadmap["phases"], "Lịch sử Đảng", False)
        print('Resources found for phases:', list(resources.keys()))
        for k, v in resources.items():
            print(f" - {k}: {len(v.get('youtube_tutorials', []))} YT, {len(v.get('web_exercises', []))} Web")
            
asyncio.run(test_roadmap())
