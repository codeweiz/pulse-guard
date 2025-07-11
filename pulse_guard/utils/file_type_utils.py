import re
from typing import Set, List

# 代码文件扩展名
CODE_EXTENSIONS: Set[str] = {
    ".py", ".vue", ".js", ".ts", ".jsx", ".tsx", ".java", ".cpp", ".c", ".h", ".hpp",
    ".go", ".rs", ".php", ".rb", ".swift", ".kt", ".scala", ".cs", ".vb", ".sql",
    ".yaml", ".yml", ".xml", ".html", ".css", ".scss", ".less", ".sh", ".bash",
    ".ps1", ".bat", ".dockerfile", ".makefile", ".md", ".txt", ".cfg", ".conf",
    ".ini", ".toml", ".properties", ".gradle", ".maven", ".sbt", ".cmake",
    ".r", ".m", ".pl", ".lua"
}

# 预编译正则表达式 - 避免重复编译提升性能
SKIP_PATTERNS: List[re.Pattern] = [
    re.compile(r".*\.(png|jpg|jpeg|gif|svg|ico|bmp|tiff|webp)$", re.IGNORECASE),
    re.compile(r".*\.(pdf|doc|docx|xls|xlsx|ppt|pptx)$", re.IGNORECASE),
    re.compile(r".*\.(zip|tar|gz|rar|7z|bz2)$", re.IGNORECASE),
    re.compile(r".*\.(mp4|avi|mov|wmv|flv|mp3|wav|ogg)$", re.IGNORECASE),
    re.compile(r"(^|.*/)node_modules/.*", re.IGNORECASE),
    re.compile(r"(^|.*/)\.git/.*", re.IGNORECASE),
    re.compile(r".*\.min\.(js|css)$", re.IGNORECASE),
    re.compile(r".*\.(lock|log)$", re.IGNORECASE),
]

# 特殊代码文件名
SPECIAL_CODE_FILES: Set[str] = {
    "makefile", "dockerfile", "rakefile", "gemfile", "podfile", "requirements.txt",
    "package-lock.json", "yarn.lock", "composer.lock", ".gitignore", ".gitattributes",
    ".dockerignore", ".eslintrc", ".prettierrc", ".babelrc", ".editorconfig",
    ".env", ".env.example", ".env.local", "license", "changelog", "contributing",
    "authors", "maintainers"
}


def is_code_file(filename: str) -> bool:
    """判断是否为代码文件"""
    # 快速检查跳过模式
    for pattern in SKIP_PATTERNS:
        if pattern.search(filename):
            return False

    # 获取文件名（去除路径）
    basename = filename.split("/")[-1].lower()

    # 检查特殊文件名
    if basename in SPECIAL_CODE_FILES:
        return True

    # 检查扩展名
    if "." in basename and not basename.startswith("."):
        ext = "." + basename.split(".")[-1].lower()
        return ext in CODE_EXTENSIONS

    return False
