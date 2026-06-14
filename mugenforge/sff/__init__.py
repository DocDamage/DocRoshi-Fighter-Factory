from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Any, Sequence, Iterable

# Constants
SFF_SIGNATURE = b'ElecbyteSpr\x00'

SFF2_IMAGE_FORMATS = {
    0: 'raw',
    1: 'linked',
    2: 'rle8',
    3: 'rle5',
    4: 'lz5',
    10: 'png8',
    11: 'png24',
    12: 'png32',
}
SFF2_DECODABLE_FORMATS = {0, 2, 10, 11, 12}
SFF2_EXPERIMENTAL_FORMATS = {3, 4}
SFF2_STANDARD_VERSIONS = {b'\x00\x00\x00\x02', b'\x00\x01\x00\x02'}
SFF2_LEGACY_LITTLE_VERSION = b'\x02\x00\x00\x00'

SFF2_FORMAT_NAMES = {
    0: 'raw',
    1: 'linked',
    2: 'rle8',
    3: 'rle5',
    4: 'lz5',
    10: 'png8',
    11: 'png24',
    12: 'png32',
}
SFF2_NAME_TO_FORMAT = {v: k for k, v in SFF2_FORMAT_NAMES.items()}


@dataclass
class SffSprite:
    index: int
    group: int
    image: int
    x: int
    y: int
    length: int
    data_offset: int
    next_offset: int
    same_palette: int = 0
    format_hint: str = 'unknown'
    comment: str = ''
    raw_header_offset: int = 0

    @property
    def key(self) -> Tuple[int, int]:
        return (self.group, self.image)


@dataclass
class SffInfo:
    path: Path
    version: Tuple[int, int, int, int]
    sprite_count: int = 0
    group_count: int = 0
    first_subfile_offset: int = 0
    subheader_size: int = 0
    palette_type: int = 0
    warnings: List[str] = field(default_factory=list)
    sprites: List[SffSprite] = field(default_factory=list)
    is_supported_for_extraction: bool = False
    variant: str = 'unknown'
    v2_metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def version_text(self) -> str:
        return '.'.join(str(v) for v in self.version)


@dataclass
class Sff2PaletteRecord:
    index: int
    group: int
    item: int
    color_count: int
    link_index: int
    data_offset: int
    data_length: int
    table_offset: int
    data_base: int
    colors: List[Tuple[int, int, int]] = field(default_factory=list)

    @property
    def num_colors(self) -> int:
        return self.color_count

    def to_dict(self) -> Dict[str, Any]:
        colors = self.colors or []
        return {
            'index': self.index,
            'group': self.group,
            'item': self.item,
            'num_colors': self.color_count,
            'color_count': self.color_count,
            'link_index': self.link_index,
            'data_offset': self.data_offset,
            'data_length': self.data_length,
            'table_offset': self.table_offset,
            'data_base': self.data_base,
            'colors': [{'index': i, 'r': int(r), 'g': int(g), 'b': int(b)} for i, (r, g, b) in enumerate(colors[:256])],
        }


@dataclass
class Sff2StandardRecord:
    index: int
    group: int
    image: int
    width: int
    height: int
    axis_x: int
    axis_y: int
    linked_index: int
    format_code: int
    color_depth: int
    data_offset: int
    data_length: int
    palette_index: int
    flags: int
    table_offset: int
    payload_offset: int
    payload_base: str = 'ldata'
    note: str = ''

    @property
    def format_name(self) -> str:
        return SFF2_FORMAT_NAMES.get(self.format_code, f'unknown-{self.format_code}')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'index': self.index,
            'group': self.group,
            'image': self.image,
            'width': self.width,
            'height': self.height,
            'axis_x': self.axis_x,
            'axis_y': self.axis_y,
            'linked_index': self.linked_index,
            'format_code': self.format_code,
            'format_name': self.format_name,
            'color_depth': self.color_depth,
            'data_offset': self.data_offset,
            'data_length': self.data_length,
            'palette_index': self.palette_index,
            'flags': self.flags,
            'table_offset': self.table_offset,
            'payload_offset': self.payload_offset,
            'payload_base': self.payload_base,
            'note': self.note,
        }


@dataclass
class Sff2ImageRecord:
    index: int
    group: int
    image: int
    width: int
    height: int
    x: int
    y: int
    link_index: int
    image_format: int
    color_depth: int
    data_offset: int
    data_length: int
    palette_index: int
    flags: int
    table_offset: int
    local_data_base: int
    translated_data_base: int
    warnings: List[str] = field(default_factory=list)

    @property
    def format_name(self) -> str:
        return SFF2_IMAGE_FORMATS.get(int(self.image_format), f'unknown-{self.image_format}')

    @property
    def is_linked(self) -> bool:
        return self.data_length == 0 or self.image_format == 1

    @property
    def decodable(self) -> bool:
        return self.image_format in SFF2_DECODABLE_FORMATS and not self.is_linked

    @property
    def key(self) -> Tuple[int, int]:
        return (self.group, self.image)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'index': self.index,
            'group': self.group,
            'image': self.image,
            'width': self.width,
            'height': self.height,
            'axis_x': self.x,
            'axis_y': self.y,
            'link_index': self.link_index,
            'image_format': self.image_format,
            'format_name': self.format_name,
            'color_depth': self.color_depth,
            'data_offset': self.data_offset,
            'data_length': self.data_length,
            'palette_index': self.palette_index,
            'flags': self.flags,
            'table_offset': self.table_offset,
            'local_data_base': self.local_data_base,
            'translated_data_base': self.translated_data_base,
            'decodable': self.decodable,
            'warnings': list(self.warnings),
        }


@dataclass
class Sff2StandardInfo:
    path: Path
    version_bytes: Tuple[int, int, int, int]
    sprite_table_offset: int
    sprite_count: int
    palette_table_offset: int
    palette_count: int
    local_data_offset: int
    local_data_length: int
    translated_data_offset: int
    translated_data_length: int
    sprites: List[Sff2ImageRecord] = field(default_factory=list)
    palettes: List[Sff2PaletteRecord] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def version_text(self) -> str:
        return '.'.join(str(v) for v in self.version_bytes)

    @property
    def decodable_count(self) -> int:
        return sum(1 for s in self.sprites if s.decodable)

    @property
    def unsupported_count(self) -> int:
        return sum(1 for s in self.sprites if not s.decodable and not s.is_linked)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'path': str(self.path),
            'version_bytes': list(self.version_bytes),
            'version_text': self.version_text,
            'sprite_table_offset': self.sprite_table_offset,
            'sprite_count': self.sprite_count,
            'palette_table_offset': self.palette_table_offset,
            'palette_count': self.palette_count,
            'local_data_offset': self.local_data_offset,
            'local_data_length': self.local_data_length,
            'translated_data_offset': self.translated_data_offset,
            'translated_data_length': self.translated_data_length,
            'decodable_count': self.decodable_count,
            'unsupported_count': self.unsupported_count,
            'sprites': [s.to_dict() for s in self.sprites],
            'palettes': [p.to_dict() for p in self.palettes],
            'warnings': list(self.warnings),
        }


from .sff_v1 import (
    _read_sff_v1_reader,
    sprite_lookup,
    try_convert_to_png,
    build_sff_v1_from_manifest,
    stage_sff_replacement_manifest,
    build_sff_v1_from_replacement_manifest,
    summarize_replacement_manifest,
    summarize_manifest_for_sff,
    export_sprite,
    export_all_sprites,
)

from .sff_v2 import (
    _inspect_sff2_header,
    patch_sff2_axis_copy,
    parse_sff2_standard,
    decode_sff2_image,
    export_sff2_decoded_images,
    build_sff2_standard_from_records,
    build_sff2_standard_from_manifest,
    summarize_sff2_standard,
    build_sff_v2_from_manifest,
    summarize_sff_detailed,
)

from .rle_lz5 import (
    decode_sff2_rle8_indices,
    encode_sff2_rle8_indices,
)


def read_sff(path: Path, max_sprites: int = 20000) -> SffInfo:
    path = Path(path)
    data = path.read_bytes()
    if len(data) >= 68 and data[:12] == SFF_SIGNATURE and data[12:16] in SFF2_STANDARD_VERSIONS:
        try:
            s2 = parse_sff2_standard(path, max_sprites=max_sprites)
            info = SffInfo(
                path=path,
                version=tuple(data[12:16]),
                sprite_count=len(s2.sprites),
                group_count=len({r.group for r in s2.sprites}),
                first_subfile_offset=s2.sprite_table_offset,
                subheader_size=28,
                palette_type=2,
                warnings=list(s2.warnings),
                variant='sff2-standard',
                is_supported_for_extraction=s2.decodable_count > 0,
                v2_metadata={
                    'sff2_standard': s2.to_dict(),
                    'header_slots': _inspect_sff2_header(data).get('header_slots', {}),
                    'supported_decode_formats': ['raw8', 'raw24', 'raw32', 'rle8', 'png8', 'png24', 'png32', 'zlib-wrapped-png'],
                    'unsupported_decode_formats': ['rle5', 'lz5'],
                },
            )
            from .sff_v2 import _mf_parse_sff2_standard, _uniq_list
            meta, records, palettes, warnings = _mf_parse_sff2_standard(data)
            info.v2_metadata.update({
                'sff2_records': [r.to_dict() for r in records[:max_sprites]],
                'sff2_record_by_index': {str(r.index): r.to_dict() for r in records[:max_sprites]},
                'sff2_palettes': [p.to_dict() for p in palettes],
                'sff2_supported_codecs': ['raw8/raw24/raw32', 'rle8', 'rle5', 'lz5', 'png8/png24/png32', 'direct/zlib pcx/png recovery'],
            })
            info.warnings = _uniq_list(info.warnings + warnings)

            for rec in s2.sprites:
                if rec.image_format in {10, 11, 12}:
                    fmt = 'png'
                elif rec.image_format == 0:
                    fmt = f'sff2_raw{rec.color_depth}'
                elif rec.image_format == 2:
                    fmt = 'sff2_rle8'
                elif rec.image_format == 3:
                    fmt = 'sff2_rle5'
                elif rec.image_format == 4:
                    fmt = 'sff2_lz5'
                elif rec.is_linked:
                    fmt = 'sff2_linked'
                else:
                    fmt = f'sff2_fmt{rec.image_format}'
                info.sprites.append(SffSprite(
                    index=rec.index,
                    group=rec.group,
                    image=rec.image,
                    x=rec.x,
                    y=rec.y,
                    length=rec.data_length,
                    data_offset=rec.data_offset,
                    next_offset=0,
                    same_palette=rec.palette_index,
                    format_hint=fmt,
                    comment=f'SFF2 {rec.format_name} {rec.width}x{rec.height} depth={rec.color_depth}',
                    raw_header_offset=rec.table_offset,
                ))
            if s2.unsupported_count:
                info.warnings.append(f'{s2.unsupported_count} SFF2 sprites use RLE5/LZ5/unsupported compression and are preserved as payloads, not production-decoded.')
            return info
        except Exception as exc:
            legacy = _read_sff_v1_reader(path, max_sprites=max_sprites)
            legacy.warnings.append(f'SFF2 standard parser failed, fell back to legacy parser: {exc}')
            return legacy
    return _read_sff_v1_reader(path, max_sprites=max_sprites)


build_sff_v2_png_from_manifest = build_sff_v2_from_manifest
