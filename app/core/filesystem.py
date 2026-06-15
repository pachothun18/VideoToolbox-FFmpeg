import os
import shutil
import tempfile
from app.config import IGNORE_DIRS, VIDEO_EXTENSIONS, SUBTITLE_EXTENSIONS, PREFERRED_LANG


class FileScanner:
    def __init__(self, ignore_dirs: set = None, video_exts: set = None,
                 subtitle_exts: set = None, preferred_lang: str = None):
        self.ignore_dirs = ignore_dirs if ignore_dirs is not None else IGNORE_DIRS
        self.video_exts = video_exts if video_exts is not None else VIDEO_EXTENSIONS
        self.subtitle_exts = subtitle_exts if subtitle_exts is not None else SUBTITLE_EXTENSIONS
        self.preferred_lang = preferred_lang if preferred_lang is not None else PREFERRED_LANG

    @staticmethod
    def create_work_dir() -> str:
        return tempfile.mkdtemp(prefix='ffmpeg_job_')

    @staticmethod
    def hardlink_or_copy(src: str, dst: str) -> str:
        try:
            os.link(src, dst)
            return 'link'
        except Exception:
            shutil.copy2(src, dst)
            return 'copy'

    def find_video_subtitle_pairs(self, root: str) -> list[tuple[str, str, str]]:
        pairs = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in self.ignore_dirs]
            videos, subs = [], []
            for f in filenames:
                ext = os.path.splitext(f)[1].lower()
                if ext in self.video_exts:
                    videos.append(f)
                elif ext in self.subtitle_exts:
                    subs.append(f)
            for v in videos:
                v_name = os.path.splitext(v)[0]
                candidates = [s for s in subs if s.lower().startswith(v_name.lower())]
                if not candidates:
                    continue
                if self.preferred_lang:
                    lang_candidates = [s for s in candidates if f'.{self.preferred_lang}-' in s or f'.{self.preferred_lang}.' in s]
                    if lang_candidates:
                        candidates = lang_candidates
                chosen = next((s for s in candidates if s.lower().endswith('.ass')), candidates[0])
                video_path = os.path.join(dirpath, v)
                sub_path = os.path.join(dirpath, chosen)
                rel_dir = os.path.relpath(dirpath, root)
                if rel_dir == '.':
                    rel_dir = ''
                pairs.append((video_path, sub_path, rel_dir))
        return pairs

    def find_videos(self, root: str) -> list[tuple[str, str]]:
        videos = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in self.ignore_dirs]
            for f in filenames:
                ext = os.path.splitext(f)[1].lower()
                if ext in self.video_exts:
                    full_path = os.path.join(dirpath, f)
                    rel_dir = os.path.relpath(dirpath, root)
                    if rel_dir == '.':
                        rel_dir = ''
                    videos.append((full_path, rel_dir))
        return videos


def create_temp_work_dir():
    return FileScanner.create_work_dir()


def create_hardlink_or_copy(src, dst):
    return FileScanner.hardlink_or_copy(src, dst)


def find_all_video_subtitle_pairs(root_dir):
    return FileScanner().find_video_subtitle_pairs(root_dir)


def find_all_videos(root_dir):
    return FileScanner().find_videos(root_dir)