<!-- PDCA标签：P.route -->
<!-- 子标签场景：Skill 安全扫描 -->
<!-- 关键词清单：安装skill/装skill/下载skill/找一个skill/有没有skill/skill推荐/技能/插件/扩展 -->
<!-- 引用范围：main + skill_mgmt_agent -->

# Skill Security & Install
> 阶段标签：P（旧标签，以头部 PDCA 标签为准）

> 版本：v1.0.0 | 更新：2026-07-08

> 📖 **什么时候读这个文件**：
> - 用户提供 GitHub 仓库 URL 并希望安装 skills
> - 用户要求"install skills from GitHub"
> - 用户希望浏览和选择仓库中的 skills
> - 需要在安装前对 skill 进行安全扫描

---

## Overview

Install Claude skills from GitHub repositories with built-in security scanning to protect against malicious code, backdoors, and vulnerabilities.

## When to Use

Trigger this skill when the user:
- Provides a GitHub repository URL and wants to install skills
- Asks to "install skills from GitHub"
- Wants to browse and select skills from a repository
- Needs to add new skills to their Claude environment

## Workflow

### Step 1: Parse GitHub URL

Accept a GitHub repository URL from the user. The URL should point to a repository containing a `skills/` directory.

Supported URL formats:
- `https://某开源仓库`
- `https://某开源仓库/tree/main/skills`
- `https://某开源仓库/tree/branch-name/skills`

Extract:
- Repository owner
- Repository name
- Branch (default to `main` if not specified)

### Step 2: Fetch Skills List

Use the WebFetch tool to retrieve the skills directory listing from GitHub.

GitHub API endpoint pattern:
```
https://api.github.com/repos/{owner}/{repo}/contents/skills?ref={branch}
```

Parse the response to extract:
- Skill directory names
- Each skill should be a subdirectory containing a SKILL.md file

### Step 3: Present Skills to User

Use the AskUserQuestion tool to let the user select which skills to install.

Set `multiSelect: true` to allow multiple selections.

Present each skill with:
- Skill name (directory name)
- Brief description (if available from SKILL.md frontmatter)

### Step 4: Fetch Skill Content

For each selected skill, fetch all files in the skill directory:

1. Get the file tree for the skill directory
2. Download all files (SKILL.md, scripts/, references/, assets/)
3. Store the complete skill content for security analysis

Use WebFetch with GitHub API:
```
https://api.github.com/repos/{owner}/{repo}/contents/skills/{skill_name}?ref={branch}
```

For each file, fetch the raw content:
```
https://raw.githubusercontent.com/{owner}/{repo}/{branch}/skills/{skill_name}/{file_path}
```

### Step 5: Security Scan

**CRITICAL:** Before installation, perform a thorough security analysis of each skill.

Examine for:
1. **Malicious Command Execution** - eval, exec, subprocess with shell=True
2. **Backdoor Detection** - obfuscated code, suspicious network requests
3. **Credential Theft** - accessing ~/.ssh, ~/.aws, environment variables
4. **Unauthorized Network Access** - external requests to suspicious domains
5. **File System Abuse** - destructive operations, unauthorized writes
6. **Privilege Escalation** - sudo attempts, system modifications
7. **Supply Chain Attacks** - suspicious package installations

Output the security analysis with:
- Security Status: SAFE / WARNING / DANGEROUS
- Risk Level: LOW / MEDIUM / HIGH / CRITICAL
- Detailed findings with file locations and severity
- Recommendation: APPROVE / APPROVE_WITH_WARNINGS / REJECT

#### SkillAudit API 扫描（推荐）

```bash
curl -s "https://skillaudit.vercel.app/scan/quick?url=https://raw.githubusercontent.com/{owner}/{repo}/{branch}/skills/{skill_name}/SKILL.md"
```

返回格式：
```json
{
  "riskLevel": "clean",
  "riskScore": 0,
  "findings": [],
  "verdict": "No issues detected."
}
```

#### 风险等级判定标准

| 等级 | 分数 | 含义 | 动作 |
|------|------|------|------|
| 🟢 `clean` | 0 | 无问题 | 自动安装 |
| 🟡 `low` | 1–9 | 轻微风险 | 提醒用户后安装 |
| 🟠 `moderate` | 10–24 | 需要手动审核 | 拒绝安装，提示手动审核 |
| 🔴 `high` | 25–49 | 高危风险 | 拒绝安装 |
| ⛔ `critical` | 50+ | 几乎肯定恶意 | 拒绝安装 |

### Step 6: User Decision

Based on the security scan results:

**If SAFE (APPROVE):**
- Proceed directly to installation

**If WARNING (APPROVE_WITH_WARNINGS):**
- Display the security warnings to the user
- Use AskUserQuestion to confirm: "Security warnings detected. Do you want to proceed with installation?"
- Options: "Yes, install anyway" / "No, skip this skill"

**If DANGEROUS (REJECT):**
- Display the critical security issues
- Refuse to install
- Explain why the skill is dangerous
- Do NOT provide an option to override for CRITICAL severity issues

### Step 7: Install Skills

For approved skills, install to the appropriate location:

| Agent | Install path |
|-------|-------------|
| Claude Code | `~/.claude/skills/{skill_name}/` |
| Codex | `~/.codex/skills/{skill_name}/` |
| Cursor | `~/.cursor/skills/{skill_name}/` |
| Other | `~/.agent/skills/{skill_name}/` |

1. Create the skill directory
2. Write all skill files maintaining the directory structure
3. Ensure proper file permissions (executable for scripts)
4. Verify SKILL.md exists and has valid frontmatter

### Step 8: Confirmation

After installation, provide a summary:
- List of successfully installed skills
- List of skipped skills (if any) with reasons
- Location of installed skills
- Next steps: "The skills are now available. Restart the agent or use them directly."

## Example Usage

**User:** "Install skills from https://某开源仓库"

**Assistant:**
1. Fetches skills list from the repository
2. Presents available skills: "skill-a", "skill-b", "skill-c"
3. User selects "skill-a" and "skill-b"
4. Performs security scan on each skill
5. skill-a: SAFE - proceeds to install
6. skill-b: WARNING (makes HTTP request) - asks user for confirmation
7. Installs approved skills
8. Confirms: "Successfully installed: skill-a, skill-b"

## Security Notes

- **Never skip security scanning** - Always analyze skills before installation
- **Be conservative** - When in doubt, flag as WARNING and let user decide
- **Critical issues are blocking** - CRITICAL severity findings cannot be overridden
- **Transparency** - Always show users what was found during security scans
- **Sandboxing** - Remind users that skills run with the agent's permissions

## 手动安全检查清单（降级方案）

如果 SkillAudit API 不可用，按以下清单手动检查：

### ☐ 1. 检查作者

- GitHub 账户已建立（不是刚创建的）
- 有其他仓库（不是单一用途账户）
- 有活跃的开源贡献
- 有头像和简介

### ☐ 2. 检查仓库活跃度

- 仓库有多次提交（不是只有初始上传）
- 最近有活动（不是已废弃）
- Issues 已启用并响应
- README 内容全面

### ☐ 3. 检查工具列表

- 没有 `bash` + `curl` 组合
- 没有 `sudo` 或 `eval`
- 工具与 skill 声明的用途匹配
- 没有不必要的工具

### ☐ 4. 检查混淆代码

- 安装脚本中没有 Base64 编码字符串
- 没有十六进制编码命令
- 没有 Unicode 技巧（零宽字符）
- 所有代码都是人类可读的

### ☐ 5. 检查环境变量访问

- 不访问密钥/凭证
- 只读取配置变量
- 不将环境变量发送到外部服务

### ☐ 6. 检查依赖

- 依赖与 skill 用途匹配
- 本地技能不需要网络工具
- 安装脚本不从外部 URL 下载
- 没有不必要的包安装

### ☐ 7. 检查安装数量和星级

- 优先选择安装量 1K+ 的 skill
- 来源信誉：`vercel-labs`、`anthropics`、`microsoft` 等官方来源更可信
- GitHub 仓库 <100 stars 的 skill 要谨慎
