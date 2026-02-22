from dataclasses import dataclass, asdict


CSV_HEADERS = [
    "Base国家",
    "公司",
    "岗位名称",
    "Base城市",
    "发布时间",
    "职业渠道",
    "职位分类",
    "职位类型",
    "职位开始时间",
    "职位结束时间",
    "具体职责",
    "要求硬技能",
    "要求软技能",
    "链接",
    "联系方式",
]


@dataclass
class Job:
    base_country: str = ""
    company: str = ""
    title: str = ""
    base_city: str = ""
    posting_date: str = ""
    channel: str = ""
    category: str = ""
    job_type: str = ""
    start_date: str = ""
    end_date: str = ""
    responsibilities: str = ""
    hard_skills: str = ""
    soft_skills: str = ""
    url: str = ""
    contact: str = ""

    def to_csv_row(self) -> dict:
        return {
            "Base国家": self.base_country,
            "公司": self.company,
            "岗位名称": self.title,
            "Base城市": self.base_city,
            "发布时间": self.posting_date,
            "职业渠道": self.channel,
            "职位分类": self.category,
            "职位类型": self.job_type,
            "职位开始时间": self.start_date,
            "职位结束时间": self.end_date,
            "具体职责": self.responsibilities,
            "要求硬技能": self.hard_skills,
            "要求软技能": self.soft_skills,
            "链接": self.url,
            "联系方式": self.contact,
        }

    def fingerprint(self) -> str:
        """Fallback identifier when URL is unavailable."""
        return f"{self.title.strip().lower()}|{self.company.strip().lower()}"

    def as_dict(self) -> dict:
        return asdict(self)
