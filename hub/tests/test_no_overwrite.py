#!/usr/bin/env python3
"""
验证同名文件在不同子目录下不会被覆盖
"""

import tempfile
import zipfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
from packager import Packager


def test_no_overwrite():
    """测试同名文件不会被覆盖"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        cache_dir = tmp / "cache"
        data_dir = tmp / "data"
        cache_dir.mkdir()
        data_dir.mkdir()
        
        # 创建子目录结构，每个目录都有同名文件 data.csv
        subdir1 = data_dir / "region_a"
        subdir2 = data_dir / "region_b"
        subdir3 = data_dir / "2024" / "q1"
        subdir1.mkdir(parents=True)
        subdir2.mkdir(parents=True)
        subdir3.mkdir(parents=True)
        
        # 创建同名文件
        (data_dir / "data.csv").write_text("root data")
        (subdir1 / "data.csv").write_text("region_a data")
        (subdir2 / "data.csv").write_text("region_b data")
        (subdir3 / "data.csv").write_text("2024 q1 data")
        
        # 打包
        packager = Packager(cache_dir=str(cache_dir))
        result = packager.package("test_dataset", str(data_dir))
        
        print(f"打包结果: success={result['success']}, file_count={result['file_count']}")
        
        # 验证 zip 内容
        with zipfile.ZipFile(result['zip_path'], 'r') as zf:
            namelist = zf.namelist()
            print(f"\nZip 内文件列表:")
            for name in namelist:
                content = zf.read(name).decode('utf-8')
                print(f"  - {name}: {content}")
            
            # 验证所有4个文件都在
            assert len(namelist) == 4, f"应该有4个文件，实际有{len(namelist)}个"
            
            # 验证路径结构
            assert "data.csv" in namelist, "根目录 data.csv 应该存在"
            assert "region_a/data.csv" in namelist, "region_a/data.csv 应该存在"
            assert "region_b/data.csv" in namelist, "region_b/data.csv 应该存在"
            assert "2024/q1/data.csv" in namelist, "2024/q1/data.csv 应该存在"
            
            # 验证内容没有被覆盖
            assert zf.read("data.csv").decode() == "root data"
            assert zf.read("region_a/data.csv").decode() == "region_a data"
            assert zf.read("region_b/data.csv").decode() == "region_b data"
            assert zf.read("2024/q1/data.csv").decode() == "2024 q1 data"
        
        print("\n✅ 测试通过: 同名文件在不同子目录下保存完整，没有相互覆盖！")
        return True


if __name__ == "__main__":
    try:
        test_no_overwrite()
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        sys.exit(1)
