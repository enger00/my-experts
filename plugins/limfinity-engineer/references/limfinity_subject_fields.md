# Limfinity 字段精确对照表（基于 43 张真实截图）

> 数据来源：`workbuddy.cn/space/d/0hqSFezUF6CABV8GGbO92V` 中 43 张 Limfinity 科目截图（已逐张多模态识别）。
> 用途：指导「妙哒小程序 × Limfinity 字段对接」。本表为**真实字段**，原方案中的"标准建议"已全部以此为准校准。
> 约定：`+新增` = 小程序 moduleConfig 需补的字段；`=已有` = 小程序已有等价字段；`×跳过` = 小程序不适用。

---

## 〇、类型映射规则（Limfinity → 小程序 FieldType）

| Limfinity 控件 | 小程序类型 | 备注 |
|---|---|---|
| 文字编辑框 | `text` | |
| 文字编辑区（长） | `textarea` | |
| 数字 | `number` | |
| 日期 | `date` | |
| 日期时间 | `text`（占位 `YYYY-MM-DD HH:mm`） | 小程序无 datetime 类型，先用 text；可选新增 `datetime` 类型 |
| 选择菜单 / 单选按钮 | `select` | 单选 |
| 列表（单选含义） | `select` | |
| 列表（多选含义） | `text` | 逗号分隔存储，避免新增组件 |
| 科目（单引用） | `person`/`equipment`/`docref`/`text` | 按引用对象定：人员→person，设备→equipment，文件目录→docref，科室等→text |
| 科目列表（多引用） | `text` | 逗号分隔 |
| 用户 | `person` | |
| 文件 | `file` | |
| 网络链接地址 | `text` | url |
| 签名板 | `file` | 签名图 |
| 代码;HTML编辑器 / 文件预览 / 流程进度 / 历史轨迹 | `×跳过` | 系统内部渲染/计算，录入端不需要 |

**通用跳过项**（所有科目）：`流程进度`（HTML）、`文件预览`（HTML）、`历史校准轨迹`（计算 ref）、系统字段（id/name/created_at/created_by/updated_by/flow_states/barcode 等）。

---

## 一、已有 32 个记录类型 × 需新增字段

### 1. 文件目录管理（doc_files，独立 documents 表，需小迁移）
`+文件编码(text)` `+生效日期(date)` `+批准人(text)` `+文件类型(select)` `+受控文件一览表(file)`
`=文件名称→title` `=版本号→version` `=文件状态→status` `=上传日期→created_at` `=文件附件→file_url`

### 2. 文件分发管理（doc_distribution）
`+受控编码(text)` `+分发编码(text)` `+分发数量(number)` `+分发人(person)`
`=受控文件名称→doc_title(docref)` `=分发对象→distribute_to` `=分发日期→distribute_date` `=说明→remark`
（接收人多选→保留现有 text 或改 person 多）

### 3. 文件废止管理（doc_abolishment）
`+受控号(text)` `+分发编号(text)` `+废止数量(number)` `+销毁日期(date)` `+销毁人(person)`
`=受控文件名称→doc_title(docref)` `=废止原因→abolish_reason` `=废止日期→abolish_date`

### 4. 合规与审批文件（compliance_file）
`+文号(text)` `+生效日期(date)` `+到期日期(date)` `+文件类型(select)` `+金额(number)`
`=文件名称→file_title` `=提交人→submitter` `=备注→remark` `=附件→attachment` `=状态→待审批`

### 5. 法规更新日志（regulation_log）
`+文件编码(text)` `+发布机构(select)` `+类型(select)` `+符合性状况(select)` `+法律法规附件(file)` `+原文链接(text)`
`=法规名称→regulation_name` `=更新日期→update_date` `=更新内容→update_content` `=来源→source` `=记录人→operator`

### 6. 人员信息管理（staff_info）
`+工号(text)` `+身份证号码(text)` `+科室(text)` `+岗位名称(text)` `+联系方式(number)` `+手机号码(text)`
`+学历证书(file)` `+学位证书(file)` `+资质证书(file)` `+职称证书(file)` `+工作人员公正性与保密承诺书(file)` `+公正性与保密性声明(file)` `+质控/中心主任/副主任岗位说明书(file)×3`
`=姓名→name` `=部门→department` `=职位→position` `=入职时间→entry_date` `=学历→education` `=备注→remark`

### 7. 来访人员登记表（visitor_register）✅ 已与 WPS 同步脚本完全印证
`+来访人数(number)` `+访问区域(text，Limfinity 为多选列表)` `+进入时间(text HH:mm)` `+离开时间(text HH:mm)` `+签名(file)`
`=来访日期→visit_date` `=来访事由→visit_purpose` `=所在单位→visitor_org(建议改标签"单位名称")` `=联系方式→contact` `=接待人→host`
（建议：`来访人姓名`标签改为`姓名`，与 Limfinity 一致）

### 8. 人员能力评审记录（competency_review）
`+评估类型(select)` `+岗位名称(text)` `+岗位评价人1(text)` `+岗位评价人2(person)` `+学历证书评估结果(select)` `+资质证书评估结果(select)` `+职称证书评估结果(select)` `+年度要求评估结果(select)` `+承诺书评估结果(select)` `+岗位资格评价人(text)` `+岗位资格评价人2(person)` `+上次评估问题是否已关闭(select)` `+是否收到反馈(select)` `+是否发生不良事件(select)` `+过往评价人(text)`
`=被评价人员→staff_name(person)` `=评审日期→review_date` `=评审内容→review_content` `=评审结果→review_result` `=评审人→reviewer`

### 9. 入职培训记录（onboarding_training）
`+岗位名称(text)` `+本次学习时长(number)` `+累计学习时长(number)` `+本次学习例数(number)` `+累计学习例数(number)` `+学员学习记录(textarea)` `+带教老师评价(textarea)` `+总结(textarea)` `+PPTRF(file)`
`=员工姓名→staff_name(person)` `=培训日期→training_date` `=培训内容→training_content` `=培训人→trainer` `=结果→result`

### 10. 人员年度培训计划（annual_training_plan）
`+培训年份(text)` `+培训课程(text)` `+计划培训时间段(text)` `+培训讲师(text)` `+培训方式(text)` `+考核方式(text)` `+备注(text)` `+培训资料(file)` `+审核人(person)` `+审核时间(text)` `+审核结果(select)` `+审核意见(text)` `+实际完成时间(date)` `+考核结果(select)` `+考核得分(number)` `+考核不合格原因(text)`
`=培训主题→plan_title` `=计划日期→plan_date` `=参与人员→participants` `=培训目标→objectives` `=状态→status`

### 11. 设备资产登记（equipment_register）
`+设备型号(text)` `+设备分类(select)` `+金额(number)` `+数量(number)` `+单位(select)` `+供应商(text)` `+生产厂家(text)` `+放置地点(text)` `+启用日期(date)` `+预计报废日期(date)` `+验收日期(date)` `+预期寿命/年(number)` `+校准周期/年(number)` `+库存状态(text)` `+验收人(person)`
`=设备名称→equipment_name` `=设备编号→equipment_no` `=设备状态→equipment_status` `=下次校准日期→next_calibration_date` `=存放位置→location` `=备注→remark`

### 12. 设备校准记录（equipment_calibration）
`+设备编号(text)` `+证书编号(text)` `+测量参数(text)` `+检测项目(text)` `+量值范围(select)` `+最大允许误差(select)` `+溯源方式(text)` `+校准机构(text)` `+校准周期/年(number)` `+结果合格(select)` `+文件附件(file)`
`=关联设备→equipment_name(equipment)` `=校准日期→calibration_date` `=校准结果→calibration_result` `=下次校准时间→next_date` `=校准人员→operator` `=备注→remark`

### 13. 实验物资出入库记录（material_inventory）
`+物资分类(select)` `+CAS号(text)` `+危险类别(text)` `+规格型号(text)` `+批号(text)` `+有效期(date)` `+品牌(text)` `+期初库存(number)` `+入库数量(number)` `+出库数量(number)` `+报废数量(number)` `+期末库存(number)` `+包装完好(select)` `+运输合规(select)` `+验收日期(date)` `+放置地点(text)`
`=物资名称→material_name` `=出入库类型→operation_type` `=数量→quantity` `=单位→unit` `=操作日期→operation_date` `=经手人→operator` `=备注→remark`

### 14. 设备维保日志（maintenance_log）
`+设备编号(text)` `+设备型号(text)` `+启用日期(date)` `+设备分类(select)` `+放置地点(text)` `+活动简要描述(text)` `+责任人(person)` `+设备履历(file)` `+验收人(person)` `+验收日期(date)` `+验收结果(select)` `+验收意见(text)`
`=关联设备→equipment_name(equipment)` `=维保日期→maintenance_date` `=维保类型→maintenance_type` `=维保内容→maintenance_content` `=维保结果→maintenance_result` `=维保人员→operator`

### 15. 环境巡查记录（env_inspection）
`+温度(text/number)` `+湿度(text/number)` `+安全巡查(text)` `+关键设备运行状态(text)`
`=巡查区域→area` `=巡查日期→inspect_date` `=巡查结果→inspect_result` `=发现问题→issues` `=巡查人员→inspector` `=备注→remark`

### 16. 环境消毒记录（disinfection_record）
`+地面及物表消毒(text)` `+紫外线消毒/h(number)` `+累计紫外使用时长(number)`
`=消毒区域→area` `=消毒日期→disinfect_date` `=消毒方式→disinfect_method` `=消毒剂→agent` `=消毒人员→operator` `=备注→remark`

### 17. 不良事件登记（adverse_event）
`+发生时间(text)` `+事件类型(text)` `+事件描述(textarea)` `+初步处理措施(textarea)` `+上报时间(text)` `+记录人(person)` `+审核人(person)` `+审核时间(text)` `+根本原因分析(textarea)` `+改进/纠正措施(textarea)` `+措施完成时间(text)` `+中心主任(person)` `+中心主任签字日期(text)` `+不良事件报告(file)`
`=事件描述→event_title` `=事件日期→event_date` `=事件类型→event_type(select)` `=严重程度→severity` `=处理措施→handling` `=上报人→reporter`

### 18. 监控系统核查记录（monitor_check）
`+检查项目(select)` `+异常情况说明(text)` `+初步处理措施(textarea)` `+审核意见(text)` `+审核人(person)` `+审核时间(text)` `+记录表(file)`
`=监控系统→system_name` `=核查日期→check_date` `=核查结果→check_result` `=核查内容→check_content` `=核查人员→checker`

### 19. 危险化学品周统计表（chemical_stat）
`+规格型号(text)` `+批号(text)` `+多个有效期(text)` `+入库数量(number)` `+净变化量(number)` `+记录总数(number)` `+第一条记录日期(date)` `+最后一条记录日期(date)`
`=化学品名称→chemical_name` `=统计周期→stat_week` `=期初库存→opening_stock` `=本周使用量→used_qty` `=期末库存→closing_stock` `=单位→unit` `=备注→remark`

### 20. 质控活动记录（qc_activity）
`+质控类型(select)` `+质控项目(select)` `+组织方/计划名称(text)` `+样本编号(text)` `+检测方法(text)` `+质控结果(text)` `+结果合格(select)` `+审核时间(text)` `+审核人(person)` `+结果判定(select)` `+趋势分析(text)` `+改进建议(text)` `+质量负责人(person)` `+质量负责人签字日期(text)` `+中心主任(person)`
`=活动名称→activity_name` `=活动日期→activity_date` `=活动内容→activity_content` `=参与人员→participants` `=活动结果→result`

### 21. 质量控制计划（quality_control_plan）
`+活动/过程(select)` `+控制项目(select)` `+控制方法(text)` `+控制频次(text)` `+接受标准(text)` `+控制记录(select)`
`=计划名称→plan_name` `=计划日期→plan_date` `=计划内容→plan_content` `=责任人→responsible` `=执行状态→status`

### 22. 方法确认验证记录（method_validation）
`+类型确认(select)` `+类型验证(空)` `+出席人员(text)` `+目的(text)` `+适用范围(text)` `+过程及结果(textarea)` `+结论(textarea)` `+审核意见(text)` `+审核人(person)` `+审核时间(text)` `+记录表(file)`
`=方法名称→method_name` `=验证日期→validation_date` `=验证内容→validation_content` `=验证结论→validation_result` `=验证人员→operator`

### 23. 风险识别与应对（risk_identification）
`+风险或机遇描述(text)` `+可能性(select)` `+严重度(select)` `+风险系数(text)` `+是否重要(select)` `+计划完成时间(date)` `+实际完成时间(date)` `+效果评估(select)` `+状态(select)` `+审核人(person)` `+审核时间(text)` `+提交管理评审(select)` `+下次评审时间(date)`
`=风险描述→risk_title` `=识别日期→identify_date` `=风险类型→risk_type` `=风险等级→risk_level` `=应对措施→response` `=责任人→responsible`

### 24. 投诉与处理记录（complaint_record）
`+联系方式(number)` `+紧急程度(select)` `+是否告知投诉人已受理(select)` `+登记日期(date)` `+调查方式(text)` `+调查结果摘要(含公正性)(textarea)` `+投诉有效性判定(select)` `+调查人(person)` `+是否已告知结果(select)` `+责任人(person)` `+审批意见(select)` `+中心主任(person)` `+中心主任签字日期(text)` `+处理结果反馈(select)` `+投诉人反馈(select)` `+投诉处理人(person)` `+步骤A~D(select)` `+评估效果(text)` `+质量负责人(person)` `+质量负责人签字日期(text)` `+记录表(file)`
`=投诉内容摘要→complaint_title` `=投诉日期→complaint_date` `=投诉详情→complaint_content` `=处理措施→handling` `=处理结果→result` `=处理人→handler`

### 25. 不符合项清单（nonconformance_item）
`+被评价人员(person)` `+不符合项事实描述(textarea)` `+不符合项识别者(person)` `+不符合项判定依据(text)` `+不符合项分级(text)` `+不符合类型(text)` `+不符合程度评估(text)` `+根本原因分析(textarea)` `+分析日期(date)` `+改进/纠正措施(textarea)` `+计划完成时间(date)` `+纠正措施完成情况(text)` `+措施完成时间(text)` `+跟踪及有效性验证(text)` `+质量负责人(person)` `+质量负责人签字日期(text)` `+审核意见(text)` `+中心主任(person)` `+中心主任签字日期(text)` `+整改状态(text)` `+内审员(person)` `+审核时间(text)`
`=不符合项描述→nc_title` `=发现日期→find_date` `=不符合类型→nc_type` `=责任人→responsible` `=整改期限→rectify_deadline` `=整改措施→correction`

### 26. 库存样本核查记录（sample_check）
`+存储设备(text)` `+冻存盒位置(text)` `+样本编码(text)` `+盒内总管数(系统)(number)` `+盒内总管数(实际)(number)` `+位置核查结果(select)` `+根本原因分析(textarea)` `+改进/纠正措施(textarea)` `+审核人(person)` `+审核时间(text)` `+质量负责人(person)` `+质量负责人签字日期(text)` `+储存设备(equipment/text)`
`=样本名称→sample_name` `=核查日期→check_date` `=样本数量→sample_count` `=核查结果→check_result` `=核查人员→checker` `=备注→remark`

### 27. 年度目标监测统计（annual_target）
`+评审年份(text)` `+目标指标(text)` `+统计公式(text)` `+监测频次(select)` `+是否达标(text/select)` `+审核人(person)` `+审核时间(text)`
`=目标名称→target_name` `=记录日期→record_date` `=监测周期→monitor_period` `=目标值→target_value` `=实际值→actual_value` `=完成情况→completion` `=备注→remark`

### 28. 战略规划记录（strategic_plan）
`+评审年份(text)` `+项目(select)` `+指标(select)` `+指标值(text)`
`=规划名称→plan_title` `=制定日期→plan_date` `=规划内容→plan_content` `=责任人→responsible` `=目标完成时间→deadline`

### 29. 文件评审会议记录（doc_review_meeting）
`+会议类型(select)` `+评审年份(text)` `+组长(person)` `+组员(text)` `+文件发放(text)` `+评审发现的主要问题(textarea)` `+评审结论(select)` `+批准人(person)` `+批准日期(text)` `+定期评审记录表(file)` `+评审范围(text)` `+评审依据(text)` `+评审方式(text)` `+整改落实情况(text)` `+执行与符合性(text)` `+文件批准发布(select)`
`=会议主题→meeting_topic` `=会议日期→meeting_date` `=参会人员→attendees` `=会议内容→meeting_content` `=会议结论→conclusion` `=主持人→host`

### 30. 管理委员会会议记录（committee_meeting）
`+地点(text)` `+会议类型(select)` `+议题(text)` `+会议决议(select)` `+利益冲突声明(text)` `+主持人(person)` `+出席人员(text)` `+缺席人员(text)` `+记录人(person)` `+批准人(person)` `+职务(select)` `+批准日期(text)` `+记录表(file)`
`=会议主题→meeting_topic` `=会议日期→meeting_date` `=参会人员→attendees` `=会议内容→meeting_content` `=会议决议→resolution` `=主持人→host`

### 31. 内部审核（internal_audit）
`+内审类型(select)` `+审核目的(textarea)` `+审核依据(textarea)` `+审核概况(textarea)` `+审核结论(textarea)` `+审核要素(text)` `+岗位名称(text)` `+内审员(person)` `+组长(person)` `+批准人(person)` `+批准日期(text)` `+责任人(person)`
`=审核范围→audit_scope` `=审核日期→audit_date` `=审核内容→audit_content` `=审核结论→audit_result` `=审核人员→auditors` `=发现问题→issues`

### 32. 管理评审（management_review）
`+评审目的(text)` `+评审范围(text)` `+评审依据(text)` `+地点(text)` `+主持人(person)` `+出席人员(text)` `+输入项1~10(text)` `+责任人1~10(person)` `+议程1~5(text)` `+批准人(person)` `+批准日期(text)` `+会议类型(select)` `+记录表(file)`
`=评审主题→review_topic` `=评审日期→review_date` `=评审内容→review_content` `=评审结论→conclusion` `=参与人员→participants`

---

## 二、小程序缺失的 Limfinity 科目（建议新增模块）

| # | Limfinity 科目 | 性质 | 建议 |
|---|---|---|---|
| A | 实验化学品及耗材 | 主数据/台账 | **新增**「化学品耗材台账」记录类型（资源资产组）：实验物资、物资分类(select)、CAS号、危险类别(text)、规格型号、单位(select)、品牌、供应商、联系人、手机号码、库存量(number) |
| B | 科室 | 主数据 | 建议新增「科室」主数据（records type `department` 或独立表），供人员/设备/会议的"科室"引用；当前小程序科室用 text 即可先不强制 |
| C | 系统配置 | 系统级 | **跳过**（环境巡查/消毒/监控的采集时间属系统后台配置，小程序无需录入） |
| D | 样本信息共享 | 业务 | **新增**「样本信息共享」模块：样本类型(select)、疾病诊断、样本数量(number)、样本状态(text)、共享条件(select)、姓名、单位名称、科室名称、手机号码、审批状态(select)、申请数量(number)、可共享样本、研究目的、样本用途(text)、合作意向(text) |
| E | 实验预约信息 | 业务 | **新增**「实验预约」模块：预约人、单位名称、科室名称、手机号码、实验类型(text)、样本类型(select)、样本数量(number)、开始时间(text)、结束时间(text)、所需仪器(text)、审核状态(select)、审核结论、审核时间(text)、审核意见、审核人员(person) |
| F | 共享样本申请记录 | 业务 | **新增**「共享样本申请」模块（与 D 关联）：姓名、单位名称、科室名称、手机号码、样本类型(select)、疾病诊断、申请数量(number)、可共享样本、研究目的、样本用途(text)、合作意向(text)、申请日期(date)、审批状态(select)、审核时间(text)、审核意见、审核结论(textarea) |
| G | 温湿度记录 | 监控 | **新增**「温湿度监控」模块（参考已落地的 Limfinity 7 仪表板，支持 29 设备）：设备名称、数据时间(text)、温度(number)、湿度(number)；建议纯 CSS 图表看板 |
| H | 门禁出入记录 | 采集 | **可选新增**「门禁记录」只读展示：门禁记录ID、姓名、工号、验证方式、刷脸时间(text)、方向(select)、设备序列号、设备IP、门禁名称、门号(select)、通行结果、抓拍图路径、入库时间(text)（多为系统自动采集，小程序以展示为主） |

---

## 三、对接范围与分期建议

- **Phase 1（常用字段，纯配置低风险）**：一、第 7/11/13/15/17/19/24/26 等高频模块的 `+新增` 字段（见上"+"项），均为 `records.content` JSONB 扩展，**无需迁移**。
- **Phase 2（扩展字段 + 文档表）**：补齐其余 `+新增`；`doc_files`(文件目录管理) 需对 `documents` 表加列（小迁移）。
- **Phase 3（新模块）**：二、A/B/D/E/F/G/H 共 8 个缺失科目，按需新建记录类型（G 温湿度可优先，复用仪表板经验）。
- **Phase 4（功能优化）**：字段级检索、首页预警卡片、字段联动、状态时间线、批量导入、字典集中管理（同原方案第五节）。

---

## 四、与原方案的差异说明

原方案第四节为"标准建议字段"（基于通用 QMS 推断）。本表已用 43 张真实截图**逐科目校准**，主要修正：
1. 来访人员登记表：证实"来访事由/访问区域"为 Limfinity **多选列表**（小程序用 text 逗号分隔），与 WPS 同步脚本 `MULTI_SELECT_FIELDS` 一致。
2. 设备/物资类：Limfinity 真实含"校准周期/年、预期寿命/年、CAS号、危险类别、量值范围、最大允许误差"等，原方案缺失。
3. 发现小程序**缺失 8 个 Limfinity 科目**（样本共享/预约、温湿度、门禁、化学品耗材台账、科室主数据），原方案未覆盖——见第二节。
4. 大量"审核人/质量负责人/中心主任/记录人"在 Limfinity 为 `科目/用户` 引用，小程序统一映射为 `person` 或 `text`。
