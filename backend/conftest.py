import os
import sys

# backend/ 를 sys.path에 추가해 "from batch.xxx import" 형태의 import가 동작하도록 한다.
# 테스트 파일 내부의 수동 sys.path.insert 를 제거할 수 있다.
sys.path.insert(0, os.path.dirname(__file__))
