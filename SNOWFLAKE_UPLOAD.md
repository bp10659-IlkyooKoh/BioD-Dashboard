# BioD Dashboard Snowflake 업로드

## 준비된 파일

`python build_snowflake_package.py`를 실행하면 다음 항목이 생성됩니다.

- `dist/BioD_Snowflake/`: 업로드할 런타임 파일 11개만 포함한 폴더
- `dist/BioD_Snowflake.zip`: 같은 파일을 담은 전달용 ZIP (압축 내부가 앱 루트)
- `dist/SHA256SUMS.txt`: 파일별 SHA-256 검증값

실험 데이터, Git 정보, 로그, 테스트, API 키는 패키지에 포함하지 않습니다.
소스 수정 후에는 위 명령을 다시 실행해야 업로드 파일도 갱신됩니다.

## Snowsight에서 실행하기

1. `BioD_Snowflake.zip`을 로컬에서 압축 해제합니다. ZIP 자체를 Excel 업로드 창에 넣지 않습니다.
2. Snowflake의 `Projects → Streamlit → + Streamlit App`에서 앱을 만듭니다.
3. `Run on warehouse`를 선택하고 사용 가능한 Database, Schema, Warehouse를 지정합니다.
   해당 위치의 USAGE 및 Schema의 CREATE STREAMLIT 권한이 필요합니다.
4. 앱 편집기에서 압축 해제한 **폴더 안 파일**을 아래 구조 그대로 업로드합니다.
   기본 `streamlit_app.py`는 제공된 파일로 교체합니다. 폴더 업로드를 지원하지 않는
   편집기에서는 `fonts` 폴더를 먼저 만들고 그 안에 세 파일을 올립니다.
5. 기본 실행 파일은 **`streamlit_app.py`**입니다. 이 파일이 매번 `app.py`를 실행합니다.
   `app.py`를 직접 실행 파일로 지정해도 됩니다.
6. `environment.yml`을 앱 루트에 둔 뒤 Run을 누릅니다.
   이 패키지는 Warehouse용이므로 Container runtime을 선택하지 않습니다.

```text
streamlit_app.py
app.py
biod_analysis.py
biod_ui.py
biod_reporting.py
biod_labels.py
biod_mollim.py
environment.yml
fonts/
  NanumGothic-Regular.ttf
  NanumGothic-Bold.ttf
  OFL.txt
```

`environment.yml`은 공식 지원 Streamlit 1.50.0과 Python 3.11을 지정합니다.
나머지는 호환 범위를 지정하며 Snowflake 채널에서 설치합니다.
`pypdf`는 테스트용이므로 런타임 패키지에서 제외했습니다.
한글 글꼴은 앱 파일 기준 경로에서 읽으며 Windows 글꼴 설치나 외부 네트워크가 필요 없습니다.
나눔고딕 재배포 조건인 OFL 라이선스 파일을 제거하지 마세요.

## 실행 후 확인

- Excel을 업로드하고 물질명과 모든 시간점이 표시되는지 확인합니다.
- Mean Table, PK, Candidate Analysis에서 같은 조건의 평균과 AUC를 비교합니다.
- 장기 비율 Excel에 모든 시간점이 포함되는지 확인합니다.
- BioD Report에서 PDF와 Excel을 내려받고 PDF 한글과 표가 표시되는지 확인합니다.

이 패키지는 배포 소스를 준비한 것이며 실제 Snowflake 계정에서의 실행은 별도 검증이 필요합니다.
패키지 설치 오류가 나면 Packages에서 Python 3.11과 해당 패키지 버전의 제공 여부,
계정의 패키지 정책을 확인하세요. 글꼴 오류는 `fonts` 폴더 경로와 파일명을 확인하세요.
Warehouse 방식의 파일 업로드 상한은 파일당 200 MB입니다.
앱 업로드만으로 실험 데이터가 Snowflake 테이블에 저장되지는 않습니다.

## 공식 문서

- 앱 생성: https://docs.snowflake.com/en/developer-guide/streamlit/app-development/creating-your-app
- 패키지 관리: https://docs.snowflake.com/en/developer-guide/streamlit/app-development/dependency-management
- 파일 구성: https://docs.snowflake.com/en/developer-guide/streamlit/app-development/file-organization
- 제한 사항: https://docs.snowflake.com/en/developer-guide/streamlit/limitations
