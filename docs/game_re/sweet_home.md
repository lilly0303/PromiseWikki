
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

> **更新日志**：增加了对 `LabelScriptLine` (标签行) 的识别，以便追踪 `Goto` 指令的具体落点。

<details>
<summary>🔻 点击展开：逻辑架构透视脚本 (C#) - V2.0</summary>

```csharp
// --- [1] 初始化输出构建器 ---
var sb = new System.Text.StringBuilder();
sb.AppendLine("《纸房子》全字段无差别透视版 (含标签) - " + System.DateTime.Now.ToString());
sb.AppendLine("--------------------------------------------------");

// --- [2] 设定目标范围 ---
var targetNames = new System.Collections.Generic.HashSet<string>() { "Script1", "Newscript", "Newscript1" };
var foundScripts = new System.Collections.Generic.List<Naninovel.Script>();

// --- [3] 锁定剧本 ---
var scripts = UnityEngine.Resources.FindObjectsOfTypeAll<Naninovel.Script>();
foreach (var s in scripts) if (targetNames.Contains(s.name)) foundScripts.Add(s);

if (foundScripts.Count == 0) {
    var loaded = UnityEngine.Resources.LoadAll<Naninovel.Script>("");
    foreach (var s in loaded) if (targetNames.Contains(s.name)) foundScripts.Add(s);
}

// --- [4] 定义核心工具 ---
System.Func<object, string> GetVal = (obj) => {
    if (obj == null) return null;
    try {
        var t = obj.GetType();
        if (!t.Namespace.StartsWith("Naninovel")) return null;
        var hv = t.GetProperty("HasValue");
        if (hv != null && !(bool)hv.GetValue(obj)) return null;
        return t.GetProperty("Value")?.GetValue(obj)?.ToString();
    } catch { return null; }
};

System.Func<object, string> InspectAllFields = (cmdObj) =>
{
    if (cmdObj == null) return "";
    var info = new System.Collections.Generic.List<string>();
    try {
        var fields = cmdObj.GetType().GetFields(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        foreach (var f in fields)
        {
            if (f.Name == "LineNumber" || f.Name == "Indent" || f.Name == "PlaybackSpot") continue;
            var valObj = f.GetValue(cmdObj);
            var strVal = GetVal(valObj);
            if (!string.IsNullOrEmpty(strVal)) info.Add($"{f.Name}=[{strVal}]");
        }
    } catch {}
    if (info.Count > 0) return " (" + string.Join(", ", info.ToArray()) + ")";
    return "";
};

// --- [5] 开始遍历 ---
foreach (var script in foundScripts)
{
    sb.AppendLine();
    sb.AppendLine($"📄 剧本: {script.name}");
    sb.AppendLine("--------------------------------------------------");
    int lineIndex = 0;
    
    foreach (var line in script.Lines)
    {
        lineIndex++;
        if (line == null) continue;
        string lType = line.GetType().Name;

        // A. 剧情文本
        if (lType == "GenericTextScriptLine")
        {
            try {
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
                        if (!string.IsNullOrEmpty(auth)) sbLine.Append(auth + "：");
                        if (!string.IsNullOrEmpty(text)) sbLine.Append(text);
                    }
                    if (sbLine.Length > 0) sb.AppendLine($"   [{lineIndex}] [剧情] " + sbLine.ToString());
                }
            } catch {}
        }
        // B. 标签 (★ 修复新增 ★)
        else if (lType == "LabelScriptLine")
        {
            try {
                var labelProp = line.GetType().GetProperty("LabelText");
                var labelVal = labelProp?.GetValue(line)?.ToString();
                if (!string.IsNullOrEmpty(labelVal))
                {
                    sb.AppendLine($"   [{lineIndex}] 🔖 [标签] {labelVal}");
                }
            } catch {}
        }
        // C. 逻辑指令
        else if (lType == "CommandScriptLine")
        {
            var cmdProp = line.GetType().GetProperty("Command");
            if (cmdProp != null)
            {
                var cmdObj = cmdProp.GetValue(line);
                if (cmdObj != null)
                {
                    string cName = cmdObj.GetType().Name;
                    string allParams = InspectAllFields(cmdObj);

                    if (cName.Contains("Choice")) sb.AppendLine($"   [{lineIndex}] 🔘 [选项] {allParams}");
                    else if (cName == "Set" || cName == "SetCustomVariable") sb.AppendLine($"   [{lineIndex}] 🔧 [变量] {allParams}");
                    else if (cName == "Goto") sb.AppendLine($"   [{lineIndex}] 🔀 [跳转] {allParams}");
                    else if (cName == "Stop") sb.AppendLine($"   [{lineIndex}] 🛑 [停止] {allParams}");
                    else if (cName == "Else" || cName == "ElseIf") sb.AppendLine($"   [{lineIndex}] 🔹 [分支判定] {cName} {allParams}");
                    else if (cName == "If" || cName == "BeginIf" || cName == "EndIf") sb.AppendLine($"   [{lineIndex}] 🔹 [逻辑块] {cName} {allParams}");
                    else if (!string.IsNullOrEmpty(allParams) && allParams.Contains("ConditionalExpression")) sb.AppendLine($"   [{lineIndex}] ⚙️ [{cName}] {allParams}");
                }
            }
        }
    }
}

// --- [6] 导出 ---
var finalContent = sb.ToString();
finalContent = finalContent.Replace("WYH", "王艺菡").Replace("LT", "陆婷").Replace("XMM", "徐敏敏").Replace("HYH", "贺老师");
finalContent = finalContent.Replace(" A ", " [进度锁A] ").Replace(" B ", " [进度锁B] ");

var desktop = System.Environment.GetFolderPath(System.Environment.SpecialFolder.Desktop);
var exportPath = System.IO.Path.Combine(desktop, "PaperHouse_XRAY_Scan_Labeled.txt");

System.IO.File.WriteAllText(exportPath, finalContent, System.Text.Encoding.UTF8);
Naninovel.Engine.Log("✅ 全字段透视提取完成！请查看: " + exportPath);

```

</details>

### 2.3 结果分析

这一步成功提取了游戏的骨架，但暴露了一个关键问题：

> **💡 发现**：生成的报告中，大量出现了类似于 `[剧情] wyh：Newscript #36.1 |#~3fb402f3|` 的内容。这是因为游戏启用了 Managed Text 模式，文本被哈希 ID 替代。

---

## 3. 第二阶段：数据挖掘 (本地化字典提取)

### 3.1 深入内存分析

为了找到“消失的文本”，我通过对象分析器（Object Inspector）追踪了 `Naninovel.Script` 对象的内部结构。经过排查，数据的真实存储路径在私有字段 `TextMap` 的嵌套对象 `idToText` 中。

### 3.2 阶段性代码 (Dictionary Dump)

<details>
<summary>🔻 点击展开：字典提取脚本 (C#)</summary>

```csharp
// --- [1] 初始化 ---
var sb = new System.Text.StringBuilder();
sb.AppendLine("《纸房子》字典文本深度提取版 - " + System.DateTime.Now.ToString());
sb.AppendLine("--------------------------------------------------");

// --- [2] 查找剧本 ---
var scripts = UnityEngine.Resources.FindObjectsOfTypeAll<Naninovel.Script>();
sb.AppendLine($"系统中共找到 {scripts.Length} 个剧本文件");

// --- [3] 钻取私有字段 ---
foreach (var script in scripts)
{
    if (script == null) continue;
    try 
    {
        // 反射获取 TextMap
        var sType = script.GetType();
        var mapField = sType.GetField("TextMap", System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance) 
                    ?? sType.GetField("textMap", System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        var mapProp = sType.GetProperty("TextMap") ?? sType.GetProperty("textMap");

        object textMapObj = null;
        if (mapProp != null) textMapObj = mapProp.GetValue(script);
        else if (mapField != null) textMapObj = mapField.GetValue(script);

        if (textMapObj != null)
        {
            // 精准打击 idToText
            var targetField = textMapObj.GetType().GetField("idToText", System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            object finalDataMap = (targetField != null) ? targetField.GetValue(textMapObj) : textMapObj;

            if (finalDataMap != null)
            {
                var dType = finalDataMap.GetType();
                var keysProp = dType.GetProperty("Keys") ?? dType.GetProperty("keys");
                var valsProp = dType.GetProperty("Values") ?? dType.GetProperty("values");

                if (keysProp != null && valsProp != null)
                {
                    var keys = keysProp.GetValue(finalDataMap) as System.Collections.Generic.ICollection<string>;
                    var vals = valsProp.GetValue(finalDataMap) as System.Collections.Generic.ICollection<string>;

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
                                if (!string.IsNullOrEmpty(kList[i])) 
                                    sb.AppendLine($"{kList[i]} = {vList[i]}");
                            }
                        }
                    }
                }
            }
        }
    }
    catch {}
}

var desktop = System.Environment.GetFolderPath(System.Environment.SpecialFolder.Desktop);
var exportPath = System.IO.Path.Combine(desktop, "PaperHouse_Dictionary_Dump.txt");
System.IO.File.WriteAllText(exportPath, sb.ToString(), System.Text.Encoding.UTF8);
Naninovel.Engine.Log("✅ 字典提取完成！文件已生成: " + exportPath);

```

</details>

---

## 4. 第三阶段：终极重构 (Runtime Linker)

### 4.1 数据清洗与合并

虽然我分别拿到了“逻辑”和“文本”，但手动比对效率极低。且剧本中的 ID 夹带元数据（如 `Newscript #36.1 |#~Hash`），导致无法直接匹配字典。

为此，我开发了最终版的**运行时连接器**，并**合入了最新的标签 (Label) 识别功能**。

### 4.2 最终解决方案代码 (All-in-One)

该脚本专为 UnityExplorer 的 REPL 环境设计，集成了**正则清洗**、**自动翻译**、**标签锚点识别**和**变量汉化**四大功能。

<details>
<summary>🔻 点击查看：全能重构工具代码 (Final Version)</summary>

```csharp
// =============================================================
//  工具名称：Naninovel 剧本自动化合并与清洗脚本 (V3.0 Final)
//  环境兼容：UnityExplorer (REPL Safe Mode)
//  核心功能：
//    1. 内存字典构建 (Memory Mapping)
//    2. 正则表达式清洗 (Regex Cleaning)
//    3. 标签锚点识别 (Label Extraction) ★修复合并★
//    4. 变量可视化翻译 (Variable Localization)
// =============================================================

// --- [1] 初始化环境 ---
var sb = new System.Text.StringBuilder();
sb.AppendLine("《纸房子》剧本完美重构报告 - " + System.DateTime.Now.ToString());
sb.AppendLine("--------------------------------------------------");

// --- [2] 构建全局哈希索引 (Global Indexing) ---
var globalTextMap = new System.Collections.Generic.Dictionary<string, string>();
var allScripts = UnityEngine.Resources.FindObjectsOfTypeAll<Naninovel.Script>();

sb.AppendLine($"[System] 检测到 {allScripts.Length} 个剧本资源，开始构建索引...");

foreach (var script in allScripts)
{
    if (script == null) continue;
    try 
    {
        // 获取 TextMap 容器
        var sType = script.GetType();
        var mapField = sType.GetField("TextMap", System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance) ?? sType.GetField("textMap", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        var mapProp = sType.GetProperty("TextMap") ?? sType.GetProperty("textMap");
        
        object textMapObj = null;
        if (mapField != null) textMapObj = mapField.GetValue(script);
        else if (mapProp != null) textMapObj = mapProp.GetValue(script);

        if (textMapObj != null)
        {
            // 钻取 idToText
            var targetField = textMapObj.GetType().GetField("idToText", System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            object finalDataMap = (targetField != null) ? targetField.GetValue(textMapObj) : textMapObj;

            if (finalDataMap != null)
            {
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
                        
                        for (int i = 0; i < kList.Count; i++)
                        {
                            string k = kList[i];
                            string v = vList[i];
                            if (!string.IsNullOrEmpty(k) && !globalTextMap.ContainsKey(k))
                                globalTextMap.Add(k, v);
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


// --- [3] 核心翻译算法 ---
System.Func<string, string> TryTranslate = (rawText) => {
    if (string.IsNullOrEmpty(rawText)) return "";
    // 1. 直接匹配
    if (globalTextMap.ContainsKey(rawText)) return globalTextMap[rawText];
    // 2. 正则清洗 (System.Text.RegularExpressions)
    var match = System.Text.RegularExpressions.Regex.Match(rawText, @"~[a-zA-Z0-9]+");
    if (match.Success)
    {
        string extractedHash = match.Value;
        if (globalTextMap.ContainsKey(extractedHash)) return globalTextMap[extractedHash];
    }
    return rawText;
};

// 辅助函数
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


// --- [4] 剧本遍历与重组 ---
foreach (var script in allScripts)
{
    // 可选：过滤
    // if (!script.name.Contains("Script")) continue;

    sb.AppendLine();
    sb.AppendLine($"📄 剧本: {script.name}");
    sb.AppendLine("--------------------------------------------------");
    int lineIndex = 0;

    foreach (var line in script.Lines)
    {
        lineIndex++;
        if (line == null) continue;
        string lType = line.GetType().Name;

        // Type A: 对话文本行
        if (lType == "GenericTextScriptLine")
        {
            try {
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
                        
                        // 翻译
                        var cleanText = TryTranslate(rawText);
                        var cleanAuth = TryTranslate(rawAuth);

                        if (!string.IsNullOrEmpty(cleanAuth)) sbLine.Append(cleanAuth + "：");
                        if (!string.IsNullOrEmpty(cleanText)) sbLine.Append(cleanText);
                    }
                    if (sbLine.Length > 0) sb.AppendLine($"   [{lineIndex:D4}] {sbLine}");
                }
            } catch {}
        }
        // Type B: 标签行 (★ 新增合并 ★)
        else if (lType == "LabelScriptLine")
        {
            try {
                var labelProp = line.GetType().GetProperty("LabelText");
                var labelVal = labelProp?.GetValue(line)?.ToString();
                if (!string.IsNullOrEmpty(labelVal))
                {
                    sb.AppendLine($"   [{lineIndex:D4}] 🔖 [标签] {labelVal}");
                }
            } catch {}
        }
        // Type C: 逻辑指令行
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
                         if (f.Name == "LineNumber" || f.Name == "Indent" || f.Name == "PlaybackSpot") continue;
                         
                         var valObj = f.GetValue(cmdObj);
                         var strVal = GetNaninovelVal(valObj);
                         
                         if (!string.IsNullOrEmpty(strVal))
                         {
                             // 尝试翻译选项文本和带 Hash 的参数
                             if (cName.Contains("Choice") && f.Name.Contains("ChoiceText")) strVal = TryTranslate(strVal);
                             else if (strVal.Contains("~")) strVal = TryTranslate(strVal);
                             
                             paramInfo.Add($"{f.Name}=[{strVal}]");
                         }
                    }
                    string allParams = string.Join(", ", paramInfo.ToArray());

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

// --- [5] 导出与后处理 ---
var finalContent = sb.ToString();

finalContent = finalContent.Replace("WYH", "王艺菡")
                           .Replace("LT", "陆婷")
                           .Replace("XMM", "徐敏敏")
                           .Replace("HYH", "贺老师")
                           .Replace("zy", "主角")
                           .Replace("Expression=", "计算: ");

var desktop = System.Environment.GetFolderPath(System.Environment.SpecialFolder.Desktop);
var exportPath = System.IO.Path.Combine(desktop, "PaperHouse_Final_Merged.txt");

System.IO.File.WriteAllText(exportPath, finalContent, System.Text.Encoding.UTF8);
Naninovel.Engine.Log("✅ 剧本完美重构完成！输出文件: " + exportPath);

```

</details>

## 5. 最终成果

通过上述工具的处理，我成功将原始的“黑盒”剧本转化为完全可读的中文文档。现在，不仅能看到对话，还能通过**标签 (Label)** 精确追踪剧情跳转的逻辑。

**🔴 处理前 (Raw Data):**

> `[36] [剧情] wyh：Newscript #36.1 |#~3fb402f3|`
> `[37] 🔘 [选项] ChoiceText=~9be251d0 GotoPath=Scene2`

**🟢 处理后 (Processed Data):**

> `[0036] 王艺菡：怎么今天早上迟到了这么久？`
> `[0037] 🔘 [选项] ChoiceText=[2017年 12月 5日] GotoPath=[Scene2]`
> `[0045] 🔖 [标签] Scene2_Start`

该方案不仅解决了本地化文本提取的问题，还为后续的攻略逻辑分析提供了最直观的数据支持。