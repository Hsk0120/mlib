"""DAG階層とメンバーの所有を扱うMaya dagContainer。"""

from .container import Container
from .transform import Transform


class DagContainer(Transform, Container):
    """Transformとしての操作と、Containerのメンバー・公開の操作を両方持つコンテナ。

    メンバー・公開の操作は、非公開の ``_ContainerMixin`` に書いたものをContainerと共有する。
    DAGの子のメンバー管理も、Maya標準の仕組みに従う。

    - removeMembersは、メンバーから外すと同時に、子を階層からも外す。
    - removeContainerは、メンバーを残したままコンテナを解除する。
      解除してもローカルの値はそのまま残るので、ワールドでの姿勢は変わることがある。

    基底クラスの例外: MayaのdagContainerはtransformの派生で、containerを継承しない。
    しかしこのクラスは、メンバー・公開の操作を共有し、``isinstance(x, Container)`` がTrueになるように、
    Containerも基底に持つ。Mayaの継承の途中にある抽象型(entity・containerBase)に対応するクラスは無い。
    つまり ``isinstance`` はMayaの継承を表さないので、継承の判定には ``isType()`` を使う。
    """
