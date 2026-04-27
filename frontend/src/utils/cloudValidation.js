// Cloud/infrastructure relevance validator for Expert Mode text answers.
// select / multiselect / boolean fields are already constrained to options and do not need this.

const CLOUD_TERMS = new Set([
  // languages & runtimes
  'python', 'java', 'nodejs', 'node', 'go', 'golang', 'ruby', 'php', 'scala', 'kotlin',
  'typescript', 'javascript', 'rust', 'csharp', '.net', 'dotnet', 'elixir', 'clojure',

  // frameworks
  'django', 'fastapi', 'flask', 'spring', 'springboot', 'laravel', 'rails', 'express',
  'nestjs', 'nextjs', 'nuxt', 'svelte', 'angular', 'react', 'vue', 'gin', 'fiber', 'actix',

  // databases
  'postgresql', 'postgres', 'mysql', 'mariadb', 'mongodb', 'mongo', 'redis', 'elasticsearch',
  'influxdb', 'clickhouse', 'sqlite', 'cassandra', 'dynamodb', 'firestore', 'cosmosdb',
  'neo4j', 'oracle', 'mssql', 'cockroachdb', 'planetscale', 'supabase', 'neon',

  // architecture patterns
  'microservices', 'microservice', 'monolith', 'monolithic', 'serverless', 'container',
  'docker', 'kubernetes', 'k8s', 'three-tier', 'two-tier', 'single_vm', 'three_tier', 'two_tier',
  'api', 'rest', 'grpc', 'graphql', 'event-driven', 'event_driven', 'data_pipeline', 'ml_pipeline',

  // infrastructure terms
  'vpc', 'cidr', 'subnet', 'subnets', 'gateway', 'nat', 'load balancer', 'loadbalancer',
  'cdn', 'waf', 'firewall', 'ssl', 'tls', 'https', 'ssh', 'bastion', 'proxy',
  'nginx', 'apache', 'haproxy', 'ingress', 'egress', 'peering', 'route53', 'dns',

  // scale & performance
  'users', 'concurrent', 'requests', 'traffic', 'throughput', 'bandwidth', 'latency',
  'rps', 'qps', 'tps', 'iops', 'replicas', 'shards', 'partitions',

  // sizing units
  'gb', 'tb', 'mb', 'kb', 'vcpu', 'vcore', 'cpu', 'ram', 'memory', 'disk', 'storage',

  // availability & reliability
  'sla', 'rpo', 'rto', 'uptime', 'failover', 'replica', 'backup', 'disaster', 'recovery',
  'multi-az', 'multi_az', 'region', 'availability', 'redundancy', 'replication',

  // budget
  'usd', 'budget', 'cost', 'monthly', 'pricing', 'spend', 'dollar',

  // cloud providers
  'aws', 'azure', 'gcp', 'digitalocean', 'linode', 'vultr', 'cloudflare', 'hetzner',
  'amazon', 'google cloud', 'alibaba cloud', 'ovh',

  // general tech concepts
  'application', 'app', 'web', 'mobile', 'backend', 'frontend', 'server', 'database', 'db',
  'nosql', 'cache', 'queue', 'broker', 'message', 'stream', 'streaming', 'batch', 'realtime',
  'pipeline', 'cluster', 'pod', 'instance', 'vm', 'compute', 'network',
  'ml', 'ai', 'model', 'analytics', 'deploy', 'deployment', 'devops', 'ci', 'cd', 'cicd',
  'environment', 'production', 'staging', 'development', 'prod', 'dev',

  // domain verticals
  'healthcare', 'fintech', 'ecommerce', 'media', 'saas', 'paas', 'iaas', 'finance', 'retail',

  // compliance
  'hipaa', 'pci', 'gdpr', 'soc2', 'compliance', 'audit', 'encryption',
])

/**
 * Returns an error string if the text answer is clearly not cloud-related,
 * or null if the answer appears valid.
 *
 * Only intended for `text` type fields where the user can type freely.
 * Short answers (< 10 chars) and answers with digits are always allowed.
 */
export function validateCloudAnswer(text) {
  const trimmed = text.trim()

  // Too short to judge — let required-field check handle emptiness
  if (trimmed.length < 10) return null

  // Any digit in the answer is almost certainly a valid infra answer
  // (user counts, CIDR, budget amounts, GB/TB, etc.)
  if (/\d/.test(trimmed)) return null

  const lower = trimmed.toLowerCase()

  // Word-boundary check against known terms
  const words = lower.split(/[\s,./\-_()]+/).filter(Boolean)
  const hasKnownTerm = words.some((word) => CLOUD_TERMS.has(word))
  if (hasKnownTerm) return null

  // Substring check — catches compound words like "postgresql" inside a sentence
  const hasSubstring = [...CLOUD_TERMS].some((term) => lower.includes(term))
  if (hasSubstring) return null

  return 'Answer does not appear cloud-related. Provide details like tech stack, architecture pattern, scale metrics, or compliance requirements.'
}
