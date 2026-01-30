
---

# 📂 Unity 逆向工程实战：Naninovel 剧本自动化提取与重构

> **项目代号**：Project SweetHome (纸房子)
> **涉及技术**：`C# Reflection` (反射机制), `Runtime Analysis` (运行时分析), `Regular Expressions` (正则匹配), `UnityExplorer`

## 1. 项目背景与挑战

在对 Unity 引擎制作的游戏《纸房子》进行逆向分析时，我试图提取游戏剧本用于攻略制作。然而，该游戏使用了 **Naninovel** 引擎的 **Managed Text（托管文本）** 机制，导致数据层出现了严重的“逻辑与内容分离”现象：

* **逻辑层**：包含跳转、变量判断，但对话内容被替换为了 `Hash ID`（如 `#~3fb402f3`）。
* **数据层**：真实的文本被加密存储在内存深处的本地化字典中。

为了还原可读的剧本，我经历了一套完整的**“侦查 -> 破解 -> 重构”**的技术迭代过程。

---

## 2. 第一阶段：黑盒透视 (逻辑架构提取)

### 2.1 初始尝试

最初，我的目标是理解剧本的基本运行逻辑。通过 UnityExplorer，我编写了一个基于反射的“透视脚本”，试图强制读取内存中 `Naninovel.Script` 对象的指令流。

此脚本的主要功能是绕过 `private` 权限，提取所有隐藏的参数值。

### 2.2 阶段性代码 (X-Ray Scan)

<details>
<summary>🔻 点击展开：逻辑架构透视脚本 (C#)</summary>

```csharp
// --- [1] 初始化输出构建器 ---
// 用于将所有提取到的信息暂时存在内存里，最后一次性导出
var sb = new System.Text.StringBuilder();
sb.AppendLine("《纸房子》全字段无差别透视版 - " + System.DateTime.Now.ToString());
sb.AppendLine("--------------------------------------------------");

// --- [2] 设定目标范围 ---
// 在这里定义你想提取的剧本文件名
var targetNames = new System.Collections.Generic.HashSet<string>() { "Script1", "Newscript", "Newscript1" };
var foundScripts = new System.Collections.Generic.List<Naninovel.Script>();

// --- [3] 锁定剧本 (双重保险) ---
// 第一步：查找当前内存中已经加载的剧本对象
var scripts = UnityEngine.Resources.FindObjectsOfTypeAll<Naninovel.Script>();
foreach (var s in scripts) if (targetNames.Contains(s.name)) foundScripts.Add(s);

// 第二步：如果内存里没找到，尝试强制从游戏资源包(Resources)里加载
if (foundScripts.Count == 0) {
    var loaded = UnityEngine.Resources.LoadAll<Naninovel.Script>("");
    foreach (var s in loaded) if (targetNames.Contains(s.name)) foundScripts.Add(s);
}

// --- [4] 定义核心工具：反射透视 (Reflection) ---
// 这是一个辅助函数，用于提取 Naninovel 特有的 "Nullable" 参数类型的值
System.Func<object, string> GetVal = (obj) => {
    if (obj == null) return null;
    try {
        var t = obj.GetType();
        // 确保只处理 Naninovel 类型的参数
        if (!t.Namespace.StartsWith("Naninovel")) return null;
        
        // 检查该参数是否有值 (HasValue)
        var hv = t.GetProperty("HasValue");
        if (hv != null && !(bool)hv.GetValue(obj)) return null;
        
        // 获取实际的值
        return t.GetProperty("Value")?.GetValue(obj)?.ToString();
    } catch { return null; }
};

// ★★★ 暴力搜身函数 ★★★
// 无论字段是公开的(Public)还是私有的(Private)，强制读取所有参数
System.Func<object, string> InspectAllFields = (cmdObj) =>
{
    if (cmdObj == null) return "";
    var info = new System.Collections.Generic.List<string>();
    
    try {
        // 获取所有字段信息
        var fields = cmdObj.GetType().GetFields(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        foreach (var f in fields)
        {
            // 过滤掉行号等无用的元数据，只看核心逻辑
            if (f.Name == "LineNumber" || f.Name == "Indent" || f.Name == "PlaybackSpot") continue;
            
            var valObj = f.GetValue(cmdObj);
            var strVal = GetVal(valObj); // 尝试解析值

            // 如果找到了有效值，就记录下来：[参数名=参数值]
            if (!string.IsNullOrEmpty(strVal))
            {
                info.Add($"{f.Name}=[{strVal}]");
            }
        }
    } catch {}

    if (info.Count > 0) return " (" + string.Join(", ", info.ToArray()) + ")";
    return "";
};

// --- [5] 开始遍历并提取 ---
foreach (var script in foundScripts)
{
    sb.AppendLine();
    sb.AppendLine($"📄 剧本: {script.name}");
    sb.AppendLine("--------------------------------------------------");
    int lineIndex = 0;
    
    // 逐行分析剧本
    foreach (var line in script.Lines)
    {
        lineIndex++;
        if (line == null) continue;
        string lType = line.GetType().Name;

        // === 类型A: 剧情文本行 ===
        if (lType == "GenericTextScriptLine")
        {
            try {
                // 深入挖掘私有的 inlinedCommands 字段
                var listField = line.GetType().GetField("inlinedCommands", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
                var list = listField?.GetValue(line) as System.Collections.IList;
                if (list != null && list.Count > 0)
                {
                    var sbLine = new System.Text.StringBuilder();
                    foreach (var cmd in list)
                    {
                        var textProp = cmd.GetType().GetField("Text");
                        var authProp = cmd.GetType().GetField("AuthorId");
                        var text = GetVal(textProp?.GetValue(cmd));
                        var auth = GetVal(authProp?.GetValue(cmd));
                        
                        // 拼接：[角色名]：[台词]
                        if (!string.IsNullOrEmpty(auth)) sbLine.Append(auth + "：");
                        if (!string.IsNullOrEmpty(text)) sbLine.Append(text);
                    }
                    if (sbLine.Length > 0) sb.AppendLine($"   [{lineIndex}] [剧情] " + sbLine.ToString());
                }
            } catch {}
        }
        // === 类型B: 逻辑指令行 ===
        else if (lType == "CommandScriptLine")
        {
            var cmdProp = line.GetType().GetProperty("Command");
            if (cmdProp != null)
            {
                var cmdObj = cmdProp.GetValue(line);
                if (cmdObj != null)
                {
                    string cName = cmdObj.GetType().Name;
                    // 直接调用上面的“暴力搜身”函数，获取该指令的所有参数
                    string allParams = InspectAllFields(cmdObj);

                    // 根据指令类型，打上不同的标记，方便阅读
                    if (cName.Contains("Choice"))
                    {
                        sb.AppendLine($"   [{lineIndex}] 🔘 [选项] {allParams}");
                    }
                    else if (cName == "Set" || cName == "SetCustomVariable")
                    {
                        sb.AppendLine($"   [{lineIndex}] 🔧 [变量] {allParams}");
                    }
                    else if (cName == "Goto")
                    {
                        sb.AppendLine($"   [{lineIndex}] 🔀 [跳转] {allParams}");
                    }
                    else if (cName == "Stop")
                    {
                        sb.AppendLine($"   [{lineIndex}] 🛑 [停止] {allParams}");
                    }
                    else if (cName == "Else" || cName == "ElseIf")
                    {
                        sb.AppendLine($"   [{lineIndex}] 🔹 [分支判定] {cName} {allParams}");
                    }
                    else if (cName == "If" || cName == "BeginIf" || cName == "EndIf")
                    {
                        sb.AppendLine($"   [{lineIndex}] 🔹 [逻辑块] {cName} {allParams}");
                    }
                    // 其他杂项指令，仅当包含条件判断(ConditionalExpression)时才显示
                    else if (!string.IsNullOrEmpty(allParams) && allParams.Contains("ConditionalExpression"))
                    {
                        sb.AppendLine($"   [{lineIndex}] ⚙️ [{cName}] {allParams}");
                    }
                }
            }
        }
    }
}

// --- [6] 导出到桌面 ---
var finalContent = sb.ToString();

// 简单的文本替换 (将代码代号替换为中文名)
finalContent = finalContent.Replace("WYH", "王艺菡").Replace("LT", "陆婷").Replace("XMM", "徐敏敏").Replace("HYH", "贺老师");
finalContent = finalContent.Replace(" A ", " [进度锁A] ").Replace(" B ", " [进度锁B] ");

// 获取桌面路径并写入文件
var desktop = System.Environment.GetFolderPath(System.Environment.SpecialFolder.Desktop);
var exportPath = System.IO.Path.Combine(desktop, "PaperHouse_XRAY_Scan.txt");

System.IO.File.WriteAllText(exportPath, finalContent, System.Text.Encoding.UTF8);
Naninovel.Engine.Log("✅ 全字段透视提取完成！请查看: " + exportPath);

```

</details>

### 2.3 结果分析

这一步成功提取了游戏的骨架，但暴露了一个关键问题：

> **💡 发现**：生成的报告中，大量出现了类似于 `[剧情] wyh：Newscript #36.1 |#~3fb402f3|` 的内容。
> * **代码含义**：这说明游戏启用了 **Managed Text（托管文本）** 模式。脚本文件中只存储了文本的索引 ID（Hash Key），而没有直接存储中文文本。
> * **现状**：虽然我掌握了所有的变量操作（如 `Expression=[王艺菡=0]`）和分支条件，但没有文本，依然无法理解剧情全貌。
> 
> 

---

## 3. 第二阶段：数据挖掘 (本地化字典提取)

### 3.1 深入内存分析

为了找到“消失的文本”，我通过对象分析器（Object Inspector）追踪了 `Naninovel.Script` 对象的内部结构。

经过排查，数据的真实存储路径如下：

1. **Script (剧本对象)**：包含逻辑指令。
2. **TextMap (映射容器)**：剧本对象中的私有字段。
3. **idToText (关键字段)**：在 `TextMap` 内部，真正的字典数据被存储在一个名为 `idToText` 的 `SerializableTextMap` 对象中。

常规的 API 无法访问这个层级，必须使用反射进行“深层钻取”。

### 3.2 阶段性代码 (Dictionary Dump)

<details>
<summary>🔻 点击展开：字典提取脚本 (C#)</summary>

```csharp
// --- [1] 初始化输出流 ---
var sb = new System.Text.StringBuilder();
sb.AppendLine("《纸房子》字典文本深度提取版 - " + System.DateTime.Now.ToString());
sb.AppendLine("--------------------------------------------------");

// --- [2] 查找内存中的剧本资源 ---
// Naninovel.Script 是 Unity 的 ScriptableObject，因此可以使用 Resources API 全局查找
var scripts = UnityEngine.Resources.FindObjectsOfTypeAll<Naninovel.Script>();
sb.AppendLine($"系统中共找到 {scripts.Length} 个剧本文件");

// --- [3] 遍历剧本并执行“钻取”操作 ---
foreach (var script in scripts)
{
    if (script == null) continue;

    try 
    {
        // === 第一层：获取 TextMap 容器 ===
        // 利用反射获取私有字段 "TextMap" 或 "textMap"
        var scriptType = script.GetType();
        var mapField = scriptType.GetField("TextMap", System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance) 
                    ?? scriptType.GetField("textMap", System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        
        // 同时也尝试获取属性 (Property)，防止字段被封装
        var mapProp = scriptType.GetProperty("TextMap") ?? scriptType.GetProperty("textMap");

        object textMapObj = null;
        if (mapProp != null) textMapObj = mapProp.GetValue(script);
        else if (mapField != null) textMapObj = mapField.GetValue(script);

        // 如果获取到了 TextMap 容器
        if (textMapObj != null)
        {
            // === 第二层：精准打击 idToText 字段 ===
            // 这是一个 SerializableTextMap 类型的内部对象，存放着真正的字典
            // 必须使用 BindingFlags.NonPublic 才能访问
            var targetField = textMapObj.GetType().GetField("idToText", System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            
            object finalDataMap = null;
            if (targetField != null)
            {
                finalDataMap = targetField.GetValue(textMapObj);
            }
            else
            {
                // 兼容性处理：如果找不到 idToText，尝试直接在当前层级查找
                finalDataMap = textMapObj;
            }

            // === 第三层：提取 Keys 和 Values 列表 ===
            if (finalDataMap != null)
            {
                var dataType = finalDataMap.GetType();
                // 动态获取 Keys 和 Values 属性（适配不同的命名规则）
                var keysProp = dataType.GetProperty("Keys") ?? dataType.GetProperty("keys");
                var valsProp = dataType.GetProperty("Values") ?? dataType.GetProperty("values");

                if (keysProp != null && valsProp != null)
                {
                    // 转换为可枚举的集合
                    var keys = keysProp.GetValue(finalDataMap) as System.Collections.Generic.ICollection<string>;
                    var vals = valsProp.GetValue(finalDataMap) as System.Collections.Generic.ICollection<string>;

                    // 导出数据
                    if (keys != null && vals != null)
                    {
                        var kList = new System.Collections.Generic.List<string>(keys);
                        var vList = new System.Collections.Generic.List<string>(vals);
                        
                        if (kList.Count > 0)
                        {
                            sb.AppendLine();
                            sb.AppendLine($"📂 剧本源 [{script.name}] - 包含 {kList.Count} 条目");
                            sb.AppendLine("--------------------------------------------------");

                            for (int i = 0; i < kList.Count; i++)
                            {
                                string k = kList[i]; // Hash ID (例如 ~3fb402f3)
                                string v = vList[i]; // 中文文本
                                
                                if (!string.IsNullOrEmpty(k))
                                {
                                    // 格式化输出：Hash = 文本
                                    sb.AppendLine($"{k} = {v}");
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    catch (System.Exception ex)
    {
        // 捕获反射过程中的异常，防止单个文件错误中断整个流程
        // sb.AppendLine($"[错误] 解析 {script.name} 失败: {ex.Message}");
    }
}

// --- [4] 导出结果至桌面 ---
var desktop = System.Environment.GetFolderPath(System.Environment.SpecialFolder.Desktop);
var exportPath = System.IO.Path.Combine(desktop, "PaperHouse_Dictionary_Dump.txt");

System.IO.File.WriteAllText(exportPath, sb.ToString(), System.Text.Encoding.UTF8);
Naninovel.Engine.Log("✅ 字典提取完成！文件已生成: " + exportPath);

```

</details>

### 3.3 结果应用

运行该脚本后，我成功提取了 Hash 到中文的映射表：

```text
~9be251d0 = 2017年 12月 5日
~3fb402f3 = 怎么今天早上迟到了这么久？
~99926b64 = 家里那堆破事呗。
...

```

---

## 4. 第三阶段：终极重构 (Runtime Linker)

### 4.1 数据清洗与合并

虽然我分别拿到了“逻辑”和“文本”，但手动比对两者极其低效。更棘手的问题是：

* **脏数据 (Dirty Data)**：逻辑层提取的 ID 往往夹带元数据（如 `Newscript #36.1 |#~3fb402f3|`），而字典里的 Key 是纯净的 `~3fb402f3`。这导致直接的字符串匹配（String Matching）失败。

为了解决这个问题，我开发了一个**运行时连接器 (Runtime Linker)**。它引入了 **正则表达式 (Regular Expressions)** 模块，在内存中动态完成“清洗”与“连接”工作。

### 4.2 最终解决方案代码

该脚本专为 UnityExplorer 的 REPL 环境设计，集成了**正则清洗**、**自动翻译**和**变量汉化**三大功能。

<details>
<summary>🔻 点击查看：全能重构工具代码 (Final Version)</summary>

```csharp
// =============================================================
//  工具名称：Naninovel 剧本自动化合并与清洗脚本
//  环境兼容：UnityExplorer (REPL Safe Mode)
//  核心功能：
//    1. 内存字典构建 (Memory Mapping)
//    2. 正则表达式清洗 (Regex Cleaning)
//    3. 变量可视化翻译 (Variable Localization)
// =============================================================

// --- [1] 初始化环境 ---
var sb = new System.Text.StringBuilder();
sb.AppendLine("《纸房子》剧本重构报告 - " + System.DateTime.Now.ToString());
sb.AppendLine("--------------------------------------------------");

// --- [2] 构建全局哈希索引 (Global Indexing) ---
// 使用 Dictionary 提供 O(1) 的查询复杂度
var globalTextMap = new System.Collections.Generic.Dictionary<string, string>();
var allScripts = UnityEngine.Resources.FindObjectsOfTypeAll<Naninovel.Script>();

sb.AppendLine($"[System] 检测到 {allScripts.Length} 个剧本资源，开始构建索引...");

foreach (var script in allScripts)
{
    if (script == null) continue;
    try 
    {
        // 反射获取 TextMap 容器 (兼容 Field 和 Property)
        var sType = script.GetType();
        var mapField = sType.GetField("TextMap", System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance) ?? sType.GetField("textMap", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        var mapProp = sType.GetProperty("TextMap") ?? sType.GetProperty("textMap");
        
        object textMapObj = null;
        if (mapField != null) textMapObj = mapField.GetValue(script);
        else if (mapProp != null) textMapObj = mapProp.GetValue(script);

        if (textMapObj != null)
        {
            // 深度钻取：定位内部的 idToText 序列化对象
            var targetField = textMapObj.GetType().GetField("idToText", System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            object finalDataMap = (targetField != null) ? targetField.GetValue(textMapObj) : textMapObj;

            if (finalDataMap != null)
            {
                // 提取键值对数据
                var dType = finalDataMap.GetType();
                var kProp = dType.GetProperty("Keys") ?? dType.GetProperty("keys");
                var vProp = dType.GetProperty("Values") ?? dType.GetProperty("values");

                if (kProp != null && vProp != null)
                {
                    var keys = kProp.GetValue(finalDataMap) as System.Collections.Generic.ICollection<string>;
                    var vals = vProp.GetValue(finalDataMap) as System.Collections.Generic.ICollection<string>;

                    if (keys != null && vals != null)
                    {
                        var kList = new System.Collections.Generic.List<string>(keys);
                        var vList = new System.Collections.Generic.List<string>(vals);
                        
                        // 填充全局字典
                        for (int i = 0; i < kList.Count; i++)
                        {
                            string k = kList[i];
                            string v = vList[i];
                            if (!string.IsNullOrEmpty(k) && !globalTextMap.ContainsKey(k))
                            {
                                globalTextMap.Add(k, v);
                            }
                        }
                    }
                }
            }
        }
    }
    catch {}
}

sb.AppendLine($"[Success] 索引构建完毕，共载入 {globalTextMap.Count} 条本地化数据。");
sb.AppendLine("--------------------------------------------------");


// --- [3] 核心翻译算法 (The Translator) ---
// 输入原始乱码字符串，输出清洗后的中文
System.Func<string, string> TryTranslate = (rawText) => {
    if (string.IsNullOrEmpty(rawText)) return "";

    // 1. 尝试直接匹配 (Exact Match)
    if (globalTextMap.ContainsKey(rawText)) return globalTextMap[rawText];

    // 2. 正则清洗 (Regex Extraction)
    // 解决 "Newscript #36.1 |#~Hash|" 无法匹配的问题
    // 使用 System.Text.RegularExpressions 避免 REPL 命名空间冲突
    var match = System.Text.RegularExpressions.Regex.Match(rawText, @"~[a-zA-Z0-9]+");
    if (match.Success)
    {
        string extractedHash = match.Value;
        if (globalTextMap.ContainsKey(extractedHash))
        {
            return globalTextMap[extractedHash]; // 返回翻译文本
        }
    }
    return rawText; // 无法翻译则保留原样
};

// 辅助函数：安全获取 Naninovel 封装值
System.Func<object, string> GetNaninovelVal = (obj) => {
    if (obj == null) return null;
    try {
        var t = obj.GetType();
        if (!t.Namespace.StartsWith("Naninovel")) return null;
        var hv = t.GetProperty("HasValue");
        if (hv != null && !(bool)hv.GetValue(obj)) return null;
        return t.GetProperty("Value")?.GetValue(obj)?.ToString();
    } catch { return null; }
};


// --- [4] 剧本遍历与重组 (Iteration & Merge) ---
foreach (var script in allScripts)
{
    // 可选：过滤掉非核心剧本
    // if (!script.name.Contains("Script") && !script.name.Contains("script")) continue;

    sb.AppendLine();
    sb.AppendLine($"📄 剧本: {script.name}");
    sb.AppendLine("--------------------------------------------------");
    int lineIndex = 0;

    foreach (var line in script.Lines)
    {
        lineIndex++;
        if (line == null) continue;
        string lType = line.GetType().Name;

        // Type A: 对话文本行 (GenericText)
        if (lType == "GenericTextScriptLine")
        {
            try {
                // 获取行内指令列表
                var listField = line.GetType().GetField("inlinedCommands", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
                var list = listField?.GetValue(line) as System.Collections.IList;
                if (list != null && list.Count > 0)
                {
                    var sbLine = new System.Text.StringBuilder();
                    foreach (var cmd in list)
                    {
                        var textProp = cmd.GetType().GetField("Text");
                        var authProp = cmd.GetType().GetField("AuthorId");
                        
                        var rawText = GetNaninovelVal(textProp?.GetValue(cmd));
                        var rawAuth = GetNaninovelVal(authProp?.GetValue(cmd));
                        
                        // 执行翻译
                        var cleanText = TryTranslate(rawText);
                        var cleanAuth = TryTranslate(rawAuth);

                        if (!string.IsNullOrEmpty(cleanAuth)) sbLine.Append(cleanAuth + "：");
                        if (!string.IsNullOrEmpty(cleanText)) sbLine.Append(cleanText);
                    }
                    if (sbLine.Length > 0) sb.AppendLine($"   [{lineIndex:D4}] {sbLine}");
                }
            } catch {}
        }
        // Type B: 逻辑指令行 (Command)
        else if (lType == "CommandScriptLine")
        {
            var cmdProp = line.GetType().GetProperty("Command");
            if (cmdProp != null)
            {
                var cmdObj = cmdProp.GetValue(line);
                if (cmdObj != null)
                {
                    string cName = cmdObj.GetType().Name;
                    var fields = cmdObj.GetType().GetFields(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
                    var paramInfo = new System.Collections.Generic.List<string>();

                    foreach (var f in fields)
                    {
                         // 过滤无关元数据
                         if (f.Name == "LineNumber" || f.Name == "Indent" || f.Name == "PlaybackSpot") continue;
                         
                         var valObj = f.GetValue(cmdObj);
                         var strVal = GetNaninovelVal(valObj);
                         
                         if (!string.IsNullOrEmpty(strVal))
                         {
                             // 特殊处理：选项文本也需要翻译
                             if (cName.Contains("Choice") && f.Name.Contains("ChoiceText")) strVal = TryTranslate(strVal);
                             // 尝试翻译任何包含 Hash 特征的参数
                             else if (strVal.Contains("~")) strVal = TryTranslate(strVal);
                             
                             paramInfo.Add($"{f.Name}=[{strVal}]");
                         }
                    }
                    string allParams = string.Join(", ", paramInfo.ToArray());

                    // 格式化输出逻辑块
                    if (cName.Contains("Choice")) sb.AppendLine($"   [{lineIndex:D4}] 🔘 [选项] {allParams}");
                    else if (cName == "Set" || cName == "SetCustomVariable") sb.AppendLine($"   [{lineIndex:D4}] 🔧 [变量] {allParams}");
                    else if (cName == "Goto") sb.AppendLine($"   [{lineIndex:D4}] 🔀 [跳转] {allParams}");
                    else if (cName == "Stop") sb.AppendLine($"   [{lineIndex:D4}] 🛑 [停止]");
                    else if (cName.StartsWith("Else")) sb.AppendLine($"   [{lineIndex:D4}] 🔹 [分支] {cName} {allParams}");
                    else if (cName.EndsWith("If")) sb.AppendLine($"   [{lineIndex:D4}] 🔹 [逻辑] {cName} {allParams}");
                }
            }
        }
    }
}

// --- [5] 数据导出与后处理 (Export & Post-Processing) ---
var finalContent = sb.ToString();

// 批量替换变量代号为中文角色名，提升可读性
finalContent = finalContent.Replace("WYH", "王艺菡")
                           .Replace("LT", "陆婷")
                           .Replace("XMM", "徐敏敏")
                           .Replace("HYH", "贺老师")
                           .Replace("zy", "主角")
                           .Replace("Expression=", "计算: ");

var desktop = System.Environment.GetFolderPath(System.Environment.SpecialFolder.Desktop);
var exportPath = System.IO.Path.Combine(desktop, "PaperHouse_Final_Translated.txt");

System.IO.File.WriteAllText(exportPath, finalContent, System.Text.Encoding.UTF8);
Naninovel.Engine.Log("✅ 剧本重构完成！输出文件: " + exportPath);

```

</details>

## 5. 最终成果

通过上述工具的处理，我成功将原始的“黑盒”剧本转化为完全可读的中文文档。

**🔴 处理前 (Raw Data):**

> `[36] [剧情] wyh：Newscript #36.1 |#~3fb402f3|`
> `[37] 🔘 [选项] ChoiceText=~9be251d0 GotoPath=Scene2`

**🟢 处理后 (Processed Data):**

> `[0036] 王艺菡：怎么今天早上迟到了这么久？`
> `[0037] 🔘 [选项] ChoiceText=[2017年 12月 5日] GotoPath=[Scene2]`

该方案不仅解决了本地化文本提取的问题，还为后续的攻略逻辑分析提供了最直观的数据支持。