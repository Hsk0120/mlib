# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""シーンのデータをJSONへ保存・復元するための部品と、複数のノードのスナップショット。

部品は2つの層に分かれる。

- 下の層: 数学型の変換(:mod:`.codec`)、ヘッダー付きのファイル(:mod:`.file`)、
  ノード・Plug・コンポーネントの参照、名前の対応づけ。
- 中の層: :class:`Snapshot` の基底クラス。

1つのノードが持つデータ(スキンウェイトなど)は、それぞれのノードのクラスのメソッドで保存する。
"""

from . import codec, file
from .animationSnapshot import AnimationSnapshot
from .attributesSnapshot import AttributesSnapshot
from .codec import decode, encode
from .componentRef import ComponentRef
from .drivenKeysSnapshot import DrivenKeysSnapshot
from .file import Header, dump, load
from .nameMapping import NameMapping
from .nodeRef import NodeRef
from .plugRef import PlugRef
from .poseSnapshot import PoseSnapshot
from .selectionSnapshot import SelectionSnapshot
from .snapshot import Snapshot, ValidationReport

__all__ = ['AnimationSnapshot', 'AttributesSnapshot', 'ComponentRef', 'DrivenKeysSnapshot', 'Header', 'NameMapping', 'NodeRef', 'PlugRef', 'PoseSnapshot', 'SelectionSnapshot', 'Snapshot', 'ValidationReport', 'codec', 'decode', 'dump', 'encode', 'file', 'load']
