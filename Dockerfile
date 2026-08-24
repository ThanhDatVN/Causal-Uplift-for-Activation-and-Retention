# Moi truong tai lap cho du an uplift nhan qua.
#
# Image chi chua CODE va DEPENDENCY. Du lieu Criteo va thu muc output duoc mount luc
# chay (xem compose.yaml), khong bake vao image:
#
#   - data/ co giay phep rieng cua Criteo, khong duoc phan phoi lai trong mot image;
#   - output/ nang 2,1 GB va phai doc duoc o trang thai THAT, khong phai ban chup
#     luc build — neu bake vao thi con so trong container va con so tren dia se troi
#     khoi nhau ma khong ai biet.
#
# Phien ban Python ghim dung 3.12 vi econml 0.16 keo tran cung scikit-learn <1.7, va
# to hop nay da duoc kiem tren dung 3.12. Doi minor version la doi ket qua.
#
# Image nang khoang 1,57 GB. Phan lon la stack khoa hoc bat buoc: scipy, numpy, pandas,
# scikit-learn, lightgbm, econml, va llvmlite 60 MB ma shap keo ve (shap la rang buoc
# cung cua econml 0.16). Co the cat them khoang 200 MB bang cach tach jupyterlab ra khoi
# requirements.txt, nhung khi do lenh cai dat trong README khong con dung cho notebook
# nua, va phai giu hai file dong bo. Danh doi khong dang, nen giu nguyen mot file.

FROM python:3.12-slim-bookworm

# libgomp1: LightGBM can OpenMP runtime, ban slim khong co san.
# Khong cai build-essential: moi dependency trong requirements.txt deu co wheel cho
# cp312 manylinux. Neu mot ngay nao do buoc nay do vi thieu trinh bien dich, hay them
# no o mot lop RIENG de lop cai dat pip van duoc cache.
RUN apt-get update \
 && apt-get install --no-install-recommends -y libgomp1 \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Copy rieng requirements truoc de lop cai dat duoc cache lai khi chi code doi.
COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
 && python -m pip install -r requirements.txt

COPY src/ ./src/
COPY scripts/ ./scripts/
COPY tests/ ./tests/
COPY webapp/ ./webapp/
COPY configs/ ./configs/
COPY docs/ ./docs/
COPY report/ ./report/
COPY planning/ ./planning/
COPY notebooks/ ./notebooks/
COPY benchmarks/ ./benchmarks/
COPY README.md requirements.txt ./

# Chay bang user thuong. Container ghi vao output/ khi chay test, nen uid phai khop
# quyen cua thu muc duoc mount; xem ghi chu trong compose.yaml.
RUN useradd --create-home --uid 1000 app \
 && chown -R app:app /app
USER app

# Mac dinh: chay tap test khong can du lieu goc. Doi command o compose de chay web app
# hoac tap test day du.
CMD ["python", "-m", "pytest", "tests", "-q", \
     "--ignore=tests/test_data.py", \
     "--ignore=tests/test_baselines.py", \
     "--ignore=tests/test_webapp.py"]
