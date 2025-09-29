#!/usr/bin/env python3
"""
간단한 Load Failed 오류 수정 검증 스크립트
=======================================

코드 파일을 직접 검사하여 수정사항이 적용되었는지 확인합니다.
"""

import os
from pathlib import Path

def verify_validation_fix():
    """검증 제약조건 수정 확인"""
    print("🔍 1. 검증 제약조건 수정 확인...")

    # response_models.py 확인
    models_file = Path("backend/models/response_models.py")
    if models_file.exists():
        with open(models_file, 'r', encoding='utf-8') as f:
            content = f.read()

        if "max_length=250" in content:
            print("  ✅ SourceInfo.content_preview max_length이 250으로 수정됨")
            model_ok = True
        else:
            print("  ❌ SourceInfo.content_preview max_length 수정 미확인")
            model_ok = False
    else:
        print("  ❌ response_models.py 파일을 찾을 수 없음")
        model_ok = False

    # rag_service.py 확인
    rag_file = Path("backend/services/rag_service.py")
    if rag_file.exists():
        with open(rag_file, 'r', encoding='utf-8') as f:
            content = f.read()

        if "content[:240]" in content:
            print("  ✅ RAG 서비스에서 content 자르기가 240으로 수정됨")
            rag_ok = True
        else:
            print("  ❌ RAG 서비스 content 자르기 수정 미확인")
            rag_ok = False
    else:
        print("  ❌ rag_service.py 파일을 찾을 수 없음")
        rag_ok = False

    return model_ok and rag_ok

def verify_form_data_fix():
    """폼 데이터 정제 수정 확인"""
    print("\n🔍 2. 폼 데이터 정제 수정 확인...")

    upload_file = Path("backend/api/upload.py")
    if upload_file.exists():
        with open(upload_file, 'r', encoding='utf-8') as f:
            content = f.read()

        checks = [
            ("clean_form_value", "폼 데이터 정제 함수 정의"),
            ("'string'", "'string' 리터럴 처리"),
            ("'none'", "'none' 리터럴 처리"),
            ("'null'", "'null' 리터럴 처리"),
            ("clean_form_value(product_family)", "product_family 정제 적용"),
            ("clean_form_value(product_model)", "product_model 정제 적용")
        ]

        all_ok = True
        for pattern, description in checks:
            if pattern in content:
                print(f"    ✅ {description} 확인됨")
            else:
                print(f"    ❌ {description} 미확인")
                all_ok = False

        return all_ok
    else:
        print("  ❌ upload.py 파일을 찾을 수 없음")
        return False

def verify_service_init_fix():
    """서비스 초기화 안전성 수정 확인"""
    print("\n🔍 3. 서비스 초기화 안전성 수정 확인...")

    vector_file = Path("backend/services/vector_service.py")
    if vector_file.exists():
        with open(vector_file, 'r', encoding='utf-8') as f:
            content = f.read()

        checks = [
            ("asyncio.wait_for", "타임아웃 처리"),
            ("timeout=30.0", "30초 타임아웃 설정"),
            ("asyncio.TimeoutError", "타임아웃 예외 처리"),
            ("except Exception as e", "일반 예외 처리"),
            ("CRITICAL: 안전한 인덱스 로드", "안전성 개선 코멘트")
        ]

        all_ok = True
        for pattern, description in checks:
            if pattern in content:
                print(f"    ✅ {description} 확인됨")
            else:
                print(f"    ❌ {description} 미확인")
                all_ok = False

        return all_ok
    else:
        print("  ❌ vector_service.py 파일을 찾을 수 없음")
        return False

def verify_error_handling_fix():
    """오류 처리 개선 확인"""
    print("\n🔍 4. 오류 처리 개선 확인...")

    rag_file = Path("backend/services/rag_service.py")
    if rag_file.exists():
        with open(rag_file, 'r', encoding='utf-8') as f:
            content = f.read()

        checks = [
            ("IMPROVED: 구체적인 오류 분류", "개선 코멘트"),
            ("validation error", "검증 오류 처리"),
            ("datatype mismatch", "데이터타입 오류 처리"),
            ("'dict' object is not callable", "서비스 초기화 오류 처리"),
            ("VALIDATION ERROR", "검증 오류 로깅"),
            ("DATABASE ERROR", "데이터베이스 오류 로깅"),
            ("SERVICE INITIALIZATION ERROR", "서비스 초기화 오류 로깅")
        ]

        all_ok = True
        for pattern, description in checks:
            if pattern in content:
                print(f"    ✅ {description} 확인됨")
            else:
                print(f"    ❌ {description} 미확인")
                all_ok = False

        return all_ok
    else:
        print("  ❌ rag_service.py 파일을 찾을 수 없음")
        return False

def verify_frontend_fix():
    """프론트엔드 오류 표시 개선 확인"""
    print("\n🔍 5. 프론트엔드 오류 표시 개선 확인...")

    frontend_file = Path("frontend/script.js")
    if frontend_file.exists():
        with open(frontend_file, 'r', encoding='utf-8') as f:
            content = f.read()

        checks = [
            ("IMPROVED: 더 구체적인 오류 메시지", "개선 코멘트"),
            ("validation", "검증 오류 메시지"),
            ("timeout", "타임아웃 오류 메시지"),
            ("connection", "연결 오류 메시지"),
            ("model", "모델 로드 오류 메시지"),
            ("initialization", "초기화 오류 메시지"),
            ("데이터 처리 중 형식 오류", "사용자 친화적 메시지"),
            ("응답 시간이 초과되었습니다", "타임아웃 사용자 메시지"),
            ("서버 연결에 문제가 있습니다", "연결 오류 사용자 메시지")
        ]

        all_ok = True
        for pattern, description in checks:
            if pattern in content:
                print(f"    ✅ {description} 확인됨")
            else:
                print(f"    ❌ {description} 미확인")
                all_ok = False

        return all_ok
    else:
        print("  ❌ script.js 파일을 찾을 수 없음")
        return False

def main():
    """모든 수정사항 검증 실행"""
    print("🚀 Load Failed 오류 수정사항 검증")
    print("=" * 50)

    tests = [
        ("검증 제약조건 수정", verify_validation_fix),
        ("폼 데이터 정제 수정", verify_form_data_fix),
        ("서비스 초기화 안전성", verify_service_init_fix),
        ("오류 처리 개선", verify_error_handling_fix),
        ("프론트엔드 개선", verify_frontend_fix)
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} 검증 중 오류: {e}")
            results.append((test_name, False))

    print("\n" + "=" * 50)
    print("📊 검증 결과 요약")
    print("=" * 50)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ 완료" if result else "❌ 미완료"
        print(f"{status} {test_name}")
        if result:
            passed += 1

    print(f"\n📈 전체 결과: {passed}/{total} 수정사항 적용됨")

    if passed == total:
        print("\n🎉 모든 수정사항이 올바르게 적용되었습니다!")
        print("\n📋 다음 단계:")
        print("   1. 서버 재시작: python backend/main.py")
        print("   2. 브라우저에서 질문 테스트")
        print("   3. 로그 확인: tail -f logs/app.log")
        return True
    else:
        print("\n⚠️ 일부 수정사항이 누락되었습니다. 추가 확인이 필요합니다.")
        return False

if __name__ == "__main__":
    result = main()
    exit(0 if result else 1)