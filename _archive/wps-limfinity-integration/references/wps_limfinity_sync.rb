# encoding: "utf-8"
# ============================================================================
# WPS 多维表 → Limfinity 一体化同步脚本（单文件、自包含）【专家参考副本】
#
# 合并自：wps_dbsheet_list_records.rb（WPS 客户端）+ visitor_sync.rb（落库逻辑）
# 语法严格遵循 Limfinity 7 Scripting Guide（create_subject / set_value / find_subjects）
#
# 实战来源：2026-08-07 完整跑通的「WPS 多维表 → Limfinity 来访人员登记表」增量同步。
# 本副本已对 WPS APP_KEY 脱敏（见下方常量），真实值保留在原项目文件
# E:\办公文件\信息化系统\limfinity\wps_limfinity_sync.rb，外部分享前请勿回填明文密钥。
#
# 用法（limfinity 命名脚本 / cron / 命令行）：
#   ruby wps_limfinity_sync.rb json          # 整表拉取存 JSON（fields 保持 WPS 原样）
#   ruby wps_limfinity_sync.rb db            # 增量同步落库到 limfinity
#
# ★ file_id / field_map / subject_type / biz_key_fields 全部在下方 __FILE__ 块里
#   作为局部变量传入，方法体内不写死，换表只改调用处即可。
# ============================================================================

# ====================== WPS 多维表格访问模块（Ruby 标准库） ======================
require 'net/http'
require 'openssl'
require 'uri'
require 'json'
require 'time'
require 'digest'

module WpsDbsheet
  HOST         = 'https://openapi.wps.cn'
  APP_ID       = 'AK20260806SAHUCM'
  APP_KEY      = '<WPS_APP_KEY>'   # 脱敏：真实值见项目原文件 wps_limfinity_sync.rb
  REDIRECT_URI = 'http://localhost:8080/callback'
  SCOPE        = 'kso.dbsheet.readwrite,kso.dbsheet.read'
  # 默认表（WPS 客户端单独使用时）。同步时由调用方传 file_id 覆盖。
  DEFAULT_FILE_ID  = '549655540491'   # 企业账号「生物样本库二附院」下的多维表
  DEFAULT_SHEET_ID = 2

  class << self
    attr_accessor :file_id, :sheet_id
  end
  self.file_id  = ENV['WPS_FILE_ID']  || DEFAULT_FILE_ID
  self.sheet_id = ENV['WPS_SHEET_ID'] ? ENV['WPS_SHEET_ID'].to_i : DEFAULT_SHEET_ID

  def self.configure(file_id: nil, sheet_id: nil)
    self.file_id  = file_id  if file_id
    self.sheet_id = sheet_id if sheet_id
    self
  end

  TOKEN_FILE   = File.expand_path('.wps_token.json', __dir__)

  def self.authorize_url
    q = URI.encode_www_form(
      client_id: APP_ID, response_type: 'code',
      redirect_uri: REDIRECT_URI, scope: SCOPE, state: 'limfinity')
    "#{HOST}/oauth2/auth?#{q}"
  end

  def self.exchange_code(code)
    data = post_token(
      grant_type: 'authorization_code', code: code,
      client_id: APP_ID, client_secret: APP_KEY, redirect_uri: REDIRECT_URI)
    persist_token(data)
    data['access_token']
  end

  def self.access_token
    tok = retrieve_token
    raise '尚未授权：先运行 WpsDbsheet.exchange_code(code)' if tok.nil? || tok['refresh_token'].to_s.empty?

    data = post_token(
      grant_type: 'refresh_token', refresh_token: tok['refresh_token'],
      client_id: APP_ID, client_secret: APP_KEY)
    persist_token(tok.merge(data))
    data['access_token']
  end

  def self.kso1_sig(method, uri, body, date)
    body_sha = body.to_s.empty? ? '' : Digest::SHA256.hexdigest(body)
    str = "KSO-1#{method}#{uri}application/json#{date}#{body_sha}"
    OpenSSL::HMAC.hexdigest('SHA256', APP_KEY, str)
  end

  def self.auth_headers(method, uri, token, body = '')
    date = Time.now.utc.strftime('%a, %d %b %Y %H:%M:%S GMT')
    sig  = kso1_sig(method, uri, body, date)
    {
      'Content-Type'         => 'application/json',
      'Authorization'        => "Bearer #{token}",
      'X-Kso-Date'          => date,
      'X-Kso-Authorization' => "KSO-1 #{APP_ID}:#{sig}"
    }
  end

  def self.get_schema(file_id = self.file_id)
    uri  = "/v7/coop/dbsheet/#{file_id}/schema"
    http_json('GET', uri, auth_headers('GET', uri, access_token))
  end

  def self.list_records(file_id = self.file_id, sheet_id = self.sheet_id, page = nil)
    uri  = "/v7/coop/dbsheet/#{file_id}/sheets/#{sheet_id}/records"
    body = { prefer_id: false, text_value: 'text', fields: [] }
    body.merge!(page) if page && !page.empty?
    body = body.to_json
    http_json('POST', uri, auth_headers('POST', uri, access_token, body), body)
  end

  def self.records_from(resp)
    d = resp['data'].is_a?(Hash) ? resp['data'] : resp
    arr = d['records'] || (d['data'] && d['data']['records']) || resp['records'] || []
    arr.is_a?(Array) ? arr : []
  end

  def self.fetch_all_records(file_id = self.file_id, sheet_id = self.sheet_id, limit = 500)
    all, offset = [], 0
    loop do
      res  = list_records(file_id, sheet_id, { offset: offset, limit: limit })
      recs = records_from(res)
      all.concat(recs)
      break if recs.size < limit
      offset += limit
    end
    { 'code' => 0, 'data' => { 'records' => all } }
  end

  def self.field_name_index(file_id = self.file_id)
    sch = get_schema(file_id)
    idx = {}
    (sch.dig('data', 'sheets') || []).each do |sh|
      (sh['fields'] || []).each { |f| idx[f['name']] = f['id'] }
    end
    idx
  end

  def self.first_sheet_id(file_id = self.file_id)
    sch = get_schema(file_id)
    sheets = sch.dig('data', 'sheets') || []
    target = sheets.find { |s| s['sheet_type'].to_s == 'xlEtDataBaseSheet' } || sheets.first
    raise "file_id=#{file_id} 未找到数据表（可能不是协作多维表类型）" if target.nil?
    target['id']
  end

  def self.records_by_file(file_id, sheet_id = nil)
    sid = sheet_id || first_sheet_id(file_id)
    fetch_all_records(file_id, sid)
  end

  def self.field_names(file_id = self.file_id)
    sch = get_schema(file_id)
    (sch.dig('data', 'sheets') || []).flat_map { |s| s['fields'] || [] }.map { |f| f['name'] }
  end

  def self.post_token(params)
    uri = URI("#{HOST}/oauth2/token")
    res = Net::HTTP.post_form(uri, params)
    JSON.parse(res.body.force_encoding('UTF-8'))
  end

  def self.http_json(method, uri, headers, body = nil)
    url  = URI("#{HOST}#{uri}")
    req  = method == 'POST' ? Net::HTTP::Post.new(url) : Net::HTTP::Get.new(url)
    headers.each { |k, v| req[k] = v }
    req.body = body if body
    res  = Net::HTTP.start(url.host, url.port, use_ssl: true, read_timeout: 30) { |h| h.request(req) }
    JSON.parse(res.body.force_encoding('UTF-8'))
  rescue => e
    { 'error' => e.message }
  end

  def self.persist_token(data)
    File.write(TOKEN_FILE, JSON.generate(data))
  end

  def self.retrieve_token
    JSON.parse(File.read(TOKEN_FILE))
  rescue StandardError
    nil
  end
end

# ====================== WPS → Limfinity 同步逻辑（参数化） ======================

# ---- WPS 字段解析（兼容 Hash / Array / 字符串三种返回）----
def extract_field(record, field_name)
  fields = record['fields']
  return nil if fields.nil?

  value = case fields
          when Hash
            fields[field_name]
          when Array
            el = fields.find { |f| f['name'] == field_name || f['field'] == field_name }
            el && el['value']
          when String
            parse_fields_string(fields)[field_name]
          end

  normalize_value(value)
end

def normalize_value(v)
  return v unless v.is_a?(Array)
  v.map { |e| e['text'] || e['name'] || e }.compact.join(', ')
end

def parse_fields_string(str)
  return {} unless str.is_a?(String) && !str.empty?

  # ★ 实测：WPS 多维表返回的 fields 是「单行紧凑 JSON」，必须用 JSON.parse！
  #   （旧实现用逐行正则解析，对单行 JSON 会整段拆成一个垃圾键 → 字段全空）
  JSON.parse(str)
rescue JSON::ParserError, StandardError
  # 兜底：兼容历史上的多行 "键":"值" 格式
  str.split("\n").each_with_object({}) do |line, h|
    line = line.strip
    next if line.empty?

    if line =~ /\A"([^"]+)"\s*:\s*"(.*)"\s*,?\z/
      h[$1] = $2.gsub('\"', '"')
    elsif line.include?(':')
      k, v = line.split(':', 2)
      h[k.to_s.strip.gsub(/^"|"$/, '')] = v.to_s.strip.gsub(/^"|"$/, '')
    end
  end
end

# WPS 一条记录 → { limfinity字段名 => 值 }（按传入的 field_map 映射）
def wps_to_hash(wps_rec, field_map)
  field_map.each_with_object({}) do |(wps_field, limf_field), h|
    h[limf_field] = extract_field(wps_rec, wps_field)
  end
end

# 业务唯一键：从 hash（WPS attrs）或 Subject（limfinity 已存在记录）里取 biz_key_fields 对应值拼成字符串
# ★ 必须兼容两种对象：Hash 用 obj[f]；limfinity Subject 用 obj.get_value(f)（Subject 不支持 [] 下标）
def biz_key(obj, biz_key_fields)
  biz_key_fields.map do |f|
    val = obj.respond_to?(:get_value) ? obj.get_value(f) : obj[f]
    (val || '').to_s
  end.join('|')
end

# 多选 Dictionary 字段：limfinity 的 set_value 不会按任何字符拆分字符串，
# 整段字符串会被当成「单个值」去查字典而报 not in the dictionary → 必须传 Ruby 数组。
# WPS 返回逗号串，这里拆成数组元素。在此列出所有多选 limfinity 字段名。
MULTI_SELECT_FIELDS = ['访问区域', '来访事由'].freeze

# 把 attrs 写入 subject（跳过空值，避免清空已有字段）
# 对多选字典字段自动拆成数组，避免 "A,B" 被当成单个非法字典项。
def set_fields(subj, attrs)
  attrs.each do |field_name, value|
    next if value.to_s.empty?
    subj.set_value(field_name, coerce_value(value, field_name))
  end
end

# 比较 limfinity 记录与待写入 attrs 是否有字段变化
# 对多选字段统一转成「排序后 ; 串」比较，避免数组 vs 字符串形式差异导致误判。
def record_changed?(rec, attrs, field_map)
  field_map.any? do |(_wps_field, limf_field)|
    comparable_value(rec.get_value(limf_field)) != comparable_value(attrs[limf_field])
  end
end

# 把字段值规范成适合 set_value 的形态
#   多选 Dictionary 字段：set_value 不拆字符串，必须传 Ruby 数组（每个元素是一项）；
#   WPS 逗号串（或已是数组）都拆成数组元素。其余字段 → 原值。
def coerce_value(value, field_name)
  return value unless MULTI_SELECT_FIELDS.include?(field_name)
  return value if value.is_a?(Array) && value.all? { |v| v.is_a?(String) }
  value.to_s.split(/[,;]/).map(&:to_s).map(&:strip).reject(&:empty?)
end

# 把任意形态的值规范成可比较的字符串
#   数组 或 含 ,/; 的字符串 → 拆数组 → 排序后 ; 拼接
#   其它 → to_s.strip
def comparable_value(value)
  arr = value.is_a?(Array) ? value : value.to_s.split(/[,;]/)
  arr.map(&:to_s).map(&:strip).reject(&:empty?).sort.join(';')
end

# ---- 模式 A：整表保存 JSON（字段名保持 WPS 原样）----
def sync_to_json(file_id:)
  resp = WpsDbsheet.records_by_file(file_id)
  recs = WpsDbsheet.records_from(resp)

  plain = recs.map do |rec|
    fields = rec['fields']
    parsed = case fields
             when Hash   then fields.transform_values { |v| normalize_value(v) }
             when Array  then fields.each_with_object({}) { |f, h| h[f['name']] = normalize_value(f['value']) }
             when String then parse_fields_string(fields)
             else {}
             end
    parsed['_record_id'] = rec['id'] if rec && rec['id']
    parsed
  end

  path = File.join(__dir__, "wps_records_#{file_id}_#{Time.now.strftime('%Y%m%d_%H%M%S')}.json")
  File.write(path, JSON.pretty_generate(plain))
  puts "[JSON 模式] 已保存 #{plain.size} 条记录到 #{path}"
  plain.size
end

# ---- 模式 B：增量同步到 limfinity（create_subject/set_value/find_subjects）----
# 只新建「新增」的、只更新「有变化」的；与系统已存在且完全相同的记录跳过不导入。
#   file_id           : WPS 多维表 file_id
#   field_map         : WPS字段名 => limfinity字段名
#   subject_type      : limfinity 科目名（如「来访人员登记表」）
#   biz_key_fields    : 组成业务唯一键的 limfinity 字段名数组（如 ['姓名','来访日期','进入时间']）
def sync_to_database(file_id:, field_map:, subject_type:, biz_key_fields:)
  wps_recs = WpsDbsheet.records_from(WpsDbsheet.records_by_file(file_id))

  # 1) 查询 limfinity 现有同科目记录（查全部记录：不要 {} 块，冒号后不加空格）
  existing = find_subjects(query:search_query(subject_type:subject_type))

  # 2) 按业务唯一键建索引
  existing_index = {}
  existing.each { |rec| existing_index[biz_key(rec, biz_key_fields)] = rec }

  added = updated = skipped = 0
  wps_recs.each do |wps_rec|
    attrs = wps_to_hash(wps_rec, field_map)
    key   = biz_key(attrs, biz_key_fields)
    exist = existing_index[key]
    rid   = wps_rec['id']

    if exist.nil?
      name_suffix = biz_key_fields.map { |f| attrs[f] }.compact.join('_')
      create_subject(subject_type, name: "WPS#{rid}_#{name_suffix}") do |s|
        set_fields(s, attrs)
      end
      added += 1
    elsif record_changed?(exist, attrs, field_map)
      set_fields(exist, attrs)
      exist.save
      updated += 1
    else
      skipped += 1                                       # 一模一样 → 跳过
    end
  end

  puts "[增量同步] 新增 #{added} 条，更新 #{updated} 条，跳过（无变化）#{skipped} 条"
  added + updated
end

# ====================== 调用处：参数在此传入 ======================
if __FILE__ == $0
  # ---- 首次授权（仅一次）：ruby wps_limfinity_sync.rb auth ----
  if ARGV[0] == 'auth'
    puts '打开下面链接完成授权，然后把地址栏 ?code= 后面的串粘贴回来：'
    puts WpsDbsheet.authorize_url
    print 'code> '
    code = STDIN.gets.to_s.strip
    WpsDbsheet.exchange_code(code)
    puts '已保存 token 到 .wps_token.json，之后可直接跑 json / db'
  else
  # ===== 换表只改下面这几行，方法体不动 =====
  file_id        = '550046787898'   # 来访人员登记表（旧表 549819725544 字段被删，2026-08-07 更换）
  field_map      = {
    '来访日期' => '来访日期',
    '姓名'     => '姓名',
    '来访人数' => '来访人数',
    '单位/部门' => '单位名称',
    '联系电话' => '联系方式',
    '来访事由' => '来访事由',
    '访问区域' => '访问区域',
    '进入时间' => '进入时间',
    '离开时间' => '离开时间',
    '请签名'   => '签名',
  }
  subject_type   = '来访人员登记表'
  biz_key_fields = ['姓名', '来访日期', '进入时间']

  mode = ARGV[0] || 'json'
  case mode
  when 'json'
    sync_to_json(file_id: file_id)
  when 'db', 'database'
    sync_to_database(file_id: file_id, field_map: field_map,
                     subject_type: subject_type, biz_key_fields: biz_key_fields)
  else
    puts "用法: ruby wps_limfinity_sync.rb [auth|json|db]"
    exit 1
  end
  end
end
