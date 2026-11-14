"""複数のscriptJobを所有者単位で管理する。"""

from contextlib import contextmanager

from .. import logger
from .scriptJob import ScriptJob


class ScriptJobs:
    """複数のscriptJobを、使う側(所有者)ごとにまとめて管理するクラス。

    オブジェクトが破棄されても、監視は自動では解除されない。
    """

    def __init__(self):
        """空の監視グループを作る。

        作った時点では何も登録しない。
        """
        self._jobs = {}
        self._temporary_active = False

    def add(self, key, **options):
        """キーに対応する監視を追加する。

        同じキーの監視がまだ登録されていれば、登録し直さずにそれを返す。

        Args:
            key (Hashable): このグループの中で重ならない識別子。
            **options (object): ScriptJobへ渡す登録の指定。

        Returns:
            ScriptJob: すでにある監視か、新しく登録した監視。すでにある場合、optionsは使わない。

        Raises:
            RuntimeError: Mayaが監視を登録できない場合。
        """
        existing = self._jobs.get(key)
        if existing is not None and existing.exists():
            return existing
        job = ScriptJob(**options)
        self._jobs[key] = job
        return job

    def exists(self):
        """このグループの監視がすべて登録されたままか調べる。

        Returns:
            bool: 監視が1つ以上あり、そのすべてが登録されたままならTrue。
        """
        return bool(self._jobs) and all(job.exists() for job in self._jobs.values())

    def stop(self):
        """このグループの監視をすべて解除する。

        解除できた監視だけをグループから取り除く。
        解除中に例外が出ても、警告を出して残りの監視の解除を続ける。
        解除できなかった監視はグループに残るので、あとでstop()を呼び直せる。
        ほかのグループの監視は解除しない。

        Raises:
            RuntimeError: 1つ以上の監視を解除できなかった場合。最初の原因の例外を__cause__に持つ。
        """
        failures = []
        for key, job in list(self._jobs.items()):
            try:
                job.stop()
            except Exception as exc:
                failures.append((key, exc))
                logger.warning("scriptJobの後始末に失敗しました(%r): %s", key, exc)
            else:
                del self._jobs[key]
        if failures:
            raise RuntimeError(f"scriptJobを停止できませんでした: {', '.join(repr(key) for key, _ in failures)}") from failures[0][1]

    @contextmanager
    def temporary(self):
        """``with`` を抜けたときに、このグループの監視を解除するコンテキストを作る。

        ``with`` に入る前から登録していた監視も解除する。UIやシーンの寿命は管理しない。
        解除できなかった監視はグループに残るので、あとでstop()を呼び直せる。
        ``with`` の中で例外が出た場合は、その例外をそのまま送出する。
        解除で出た例外に置き換えることはない。

        Yields:
            ScriptJobs: 自身。

        Raises:
            RuntimeError: 同じオブジェクトで入れ子にした場合、または ``with`` の中が正常に終わったのに
                解除に失敗した場合。
        """
        if self._temporary_active:
            raise RuntimeError("同じインスタンスでScriptJobs.temporaryを入れ子にはできません")
        self._temporary_active = True
        body_failed = False
        try:
            try:
                yield self
            except BaseException:
                body_failed = True
                raise
        finally:
            try:
                self.stop()
            except Exception:
                if not body_failed:
                    raise
            finally:
                self._temporary_active = False
