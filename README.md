# object.json格式转换到usda

首先得到的是在pm或者hssd_data下面的子模型文件，形如下图这样的结构

<img width="505" height="469" alt="object" src="https://github.com/user-attachments/assets/adb40405-0075-4d3a-8ade-0cd9aac1da7d" />

## 前提需求：

安装了isaacsim和isaaclab

## 项目文件夹说明:
- change_format/batch_run: 批量转换脚本
- example: 转换成功的示例

## object.json转换为URDF并FIX

然后需要对object.json进行处理转换（在object.json中规定了关节的关系和位置角度等信息）。

然后再把其转换为urdf文件：调用的文件是**convert_object_json_to_urdf_pm.py**，和一个批量转换的脚本**run_conversion.py**。

随后需要对转换后的urdf文件进行检查，排除几何上的错误，这里运行的是**geom_fixing.py**文件。此外还发现应当再把其obj文件的名字从"-"变为"_"否则后面有可能会出现导入物体部分缺失的情况，这里用的python脚本是rename_obj_files_batch.py。

## URDF转换为XML并FIX

把urdf再转换为XML文件，用的指令是

```bash
urdf2mjcf model.urdf model.xml.
```

urdf2mjcf来自仓库**WIKI-GRX-MJCF**。需要git clone下来：

```bash
git clone https://github.com/FFTAI/Wiki-GRx-MJCF.git
```

随后还需要把XML文件进行处理，把obj的绝对路径转化为相对路径，在此需要调用fix_xml.py文件。fixed的结果如下所示：

<img width="2112" height="815" alt="xml" src="https://github.com/user-attachments/assets/e91a3e69-3fb2-4690-85fb-fca8c0ab6429" />

注意进行转化需要在模型文件夹路径下面。

## XML转化为USDA文件

XML转化为USDA文件应当调用的是isaaclab的官方脚本，**convert_mjcf.py**，例如：

```bash
python ./convert_mjcf.py model_fixed.xml model.usda。
```

现在的USDA打开就是正常的了：

<img width="2478" height="1332" alt="usda" src="https://github.com/user-attachments/assets/96dc6251-fbac-4544-8007-37b2368f94ce" />

## 批量转换脚本说明
一共写了五个批量转换脚本。分别对应这五个步骤：
- 1.转换所有object.json为urdf:**convert_json_to_urdf_batch.py**
- 2.修复转换后的urdf和.obj文件中的几何错误:**fix_urdf_geoms_batch.py**
- 3.把obj文件路径中的"-"变为"_":**rename_obj_files_batch.py**
- 4.转换所有urdf为xml:**convert_urdf_to_xml_batch.py**
- 5.修复所有xml中的obj路径从绝对路径变为相对路径:**fix_xml_batch.sh**
- 6.转换所有xml为usda:**convert_xml_to_usda_batch.py**

注意：对于上面所有的批量处理脚本，都是不设置输入参数的，在使用前应当对其中的路径等信息自行处理。
## 转换成功的示例：
在examples下有两个成功的示例，可以从中进行学习。其中的pm来自于sapien平台的开源数据集，而hssd_data来自于hssd数据集。在转换成功的文件中可以看见如下的列表信息:
- configuration文件夹：存放了组件usd和材质等文件
- features文件夹：
- imgs文件夹:
- objs文件夹:存放了组件的points数据。其中有.obj,.mtl,.obj.bak(修改了obj后的备份文件)
- plys文件夹:
- textures文件夹:
- model_fixed.urdf:转换后的urdf文件
- model_fixed.xml:转换后的xml文件
- model_fixed1.xml:修改obj绝对路径为相对路径后的xml文件
- model_fixed1.usda:转换成功的usda文件
- object.json:转换前的json文件
