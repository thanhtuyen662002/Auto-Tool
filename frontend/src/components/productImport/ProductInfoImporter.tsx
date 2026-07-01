import { useMemo, useState } from 'react';
import { importProductInfo } from '../../api/client';
import type {
  IndustryPreset,
  ProductImportInputType,
  ProductImportResult,
  ProductInfoNormalized,
  ProductValidationIssue,
} from '../../types/project';
import ApiErrorBox from '../ApiErrorBox';
import NotifyOnChange from '../notifications/NotifyOnChange';
import TextArea from '../TextArea';

const IMPORT_TABS: Array<{ id: ProductImportInputType; label: string; placeholder: string }> = [
  {
    id: 'manual',
    label: 'Nhập thủ công',
    placeholder: '',
  },
  {
    id: 'text',
    label: 'Dán mô tả sản phẩm',
    placeholder: 'Dán mô tả, thông số, lợi ích, giá bán hoặc nội dung sản phẩm mà bạn đang có.',
  },
  {
    id: 'txt',
    label: 'Chọn file mô tả',
    placeholder: 'Dán nội dung file mô tả sản phẩm hoặc chọn file .txt bên dưới.',
  },
];

interface ProductInfoImporterProps {
  industryPresets: IndustryPreset[];
  onApply: (product: ProductInfoNormalized) => Promise<void> | void;
}

export default function ProductInfoImporter({ industryPresets, onApply }: ProductInfoImporterProps) {
  const [activeTab, setActiveTab] = useState<ProductImportInputType>('manual');
  const [content, setContent] = useState('');
  const [sourceName, setSourceName] = useState<string | null>(null);
  const [result, setResult] = useState<ProductImportResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const active = IMPORT_TABS.find((tab) => tab.id === activeTab) ?? IMPORT_TABS[0];
  const suggestedIndustry = useMemo(() => {
    const presetId = result?.product?.industry_preset_id;
    if (!presetId) return null;
    return industryPresets.find((preset) => preset.id === presetId) ?? null;
  }, [industryPresets, result?.product?.industry_preset_id]);

  async function handleAnalyze() {
    if (activeTab === 'manual') return;
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const response = await importProductInfo({
        input_type: activeTab,
        raw_text: content,
        file_content: content,
        source_name: sourceName,
      });
      setResult(response);
      setMessage('Đã phân tích thông tin sản phẩm.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể phân tích thông tin sản phẩm.');
    } finally {
      setLoading(false);
    }
  }

  async function handleFile(file: File | null) {
    if (!file) return;
    setSourceName(file.name);
    setContent(await file.text());
  }

  async function handleApply() {
    if (!result?.product) return;
    setApplying(true);
    setError(null);
    setMessage(null);
    try {
      await onApply(result.product);
      setMessage('Đã áp dụng thông tin sản phẩm vào project.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể áp dụng thông tin sản phẩm.');
    } finally {
      setApplying(false);
    }
  }

  function resetImport() {
    setContent('');
    setSourceName(null);
    setResult(null);
    setError(null);
    setMessage(null);
  }

  return (
    <div className="rounded-lg border border-line bg-surface/70 p-4">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">Import thông tin sản phẩm</h2>
          <p className="mt-1 text-sm text-muted">
            Dùng khi bạn đã có mô tả sản phẩm. Tool chỉ sắp xếp lại thông tin, không tự xác minh thông số.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {IMPORT_TABS.map((tab) => (
          <button
            className={`rounded-md border px-3 py-2 text-sm font-semibold ${
              activeTab === tab.id
                ? 'border-brand bg-brand text-white'
                : 'border-line bg-white text-ink hover:border-brand'
            }`}
            key={tab.id}
            type="button"
            onClick={() => {
              setActiveTab(tab.id);
              setResult(null);
              setError(null);
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'manual' ? (
        <p className="mt-4 rounded-md border border-line bg-white px-3 py-3 text-sm text-muted">
          Dùng form bên dưới để nhập thủ công. Các tab còn lại dùng khi bạn muốn paste mô tả hoặc import nội dung file.
        </p>
      ) : (
        <div className="mt-4 space-y-3">
          <TextArea
            label={active.label}
            value={content}
            rows={8}
            placeholder={active.placeholder}
            onChange={setContent}
          />
          <div className="flex flex-wrap items-center gap-3">
            {activeTab === 'txt' ? (
              <label className="rounded-md border border-line bg-white px-3 py-2 text-sm font-semibold text-ink hover:border-brand">
                Chọn file
                <input
                  className="hidden"
                  type="file"
                  accept=".txt,text/plain"
                  onChange={(event) => void handleFile(event.target.files?.[0] ?? null)}
                />
              </label>
            ) : null}
            {sourceName ? <span className="text-xs text-muted">File: {sourceName}</span> : null}
            <button
              className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:hover:bg-brand"
              type="button"
              disabled={loading || !content.trim()}
              onClick={() => void handleAnalyze()}
            >
              {loading ? 'Đang phân tích...' : 'Phân tích thông tin sản phẩm'}
            </button>
          </div>
        </div>
      )}

      <ApiErrorBox error={error} />
      <NotifyOnChange value={message} variant="success" />

      {result ? (
        <div className="mt-4 rounded-md border border-line bg-white p-4">
          {result.product ? (
            <ImportPreview
              product={result.product}
              issues={result.issues}
              industryName={suggestedIndustry?.name ?? result.product.industry_preset_id ?? 'Chưa rõ'}
            />
          ) : (
            <IssueList issues={result.issues} />
          )}

          <div className="mt-4 flex flex-wrap gap-3">
            <button
              className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
              type="button"
              disabled={!result.product || !result.success || applying}
              onClick={() => void handleApply()}
            >
              {applying ? 'Đang áp dụng...' : 'Áp dụng vào project'}
            </button>
            <button
              className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
              type="button"
              onClick={() => setActiveTab('manual')}
            >
              Chỉnh sửa thủ công
            </button>
            <button
              className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-muted hover:border-brand"
              type="button"
              onClick={resetImport}
            >
              Hủy
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ImportPreview({
  product,
  issues,
  industryName,
}: {
  product: ProductInfoNormalized;
  issues: ProductValidationIssue[];
  industryName: string;
}) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <SummaryItem label="Tên sản phẩm" value={product.name || 'Thiếu'} />
        <SummaryItem label="Thương hiệu" value={product.brand || 'Chưa có'} />
        <SummaryItem label="Lời kêu gọi hành động" value={product.cta} />
        <SummaryItem label="Ngành hàng gợi ý" value={industryName} />
        <SummaryItem label="Độ tin cậy" value={`${Math.round(product.confidence_score * 100)}%`} />
      </div>
      <SummaryBlock label="Mô tả" value={product.description || 'Chưa có mô tả'} />
      <BulletBlock label="Điểm nổi bật" items={product.features} empty="Chưa có điểm nổi bật." />
      <BulletBlock
        label="Thông số"
        items={product.specs.map((spec) => `${spec.name}: ${spec.value}`)}
        empty="Chưa có thông số."
      />
      <BulletBlock label="Hashtag gợi ý" items={product.hashtag_suggestions} empty="Chưa có hashtag gợi ý." />
      <IssueList issues={issues} />
    </div>
  );
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-surface px-3 py-2">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-1 text-sm text-ink">{value}</div>
    </div>
  );
}

function SummaryBlock({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="mb-1 text-sm font-semibold text-ink">{label}</div>
      <p className="rounded-md bg-surface px-3 py-2 text-sm text-ink">{value}</p>
    </div>
  );
}

function BulletBlock({ label, items, empty }: { label: string; items: string[]; empty: string }) {
  return (
    <div>
      <div className="mb-1 text-sm font-semibold text-ink">{label}</div>
      {items.length ? (
        <ul className="space-y-1 rounded-md bg-surface px-4 py-3 text-sm text-ink">
          {items.map((item, index) => (
            <li key={`${item}-${index}`}>- {item}</li>
          ))}
        </ul>
      ) : (
        <p className="rounded-md bg-surface px-3 py-2 text-sm text-muted">{empty}</p>
      )}
    </div>
  );
}

function IssueList({ issues }: { issues: ProductValidationIssue[] }) {
  if (!issues.length) return null;
  return (
    <div>
      <div className="mb-1 text-sm font-semibold text-ink">Cảnh báo</div>
      <ul className="space-y-2">
        {issues.map((issue, index) => (
          <li
            className={`rounded-md border px-3 py-2 text-sm ${
              issue.severity === 'error'
                ? 'border-red-200 bg-red-50 text-red-700'
                : issue.severity === 'warning'
                  ? 'border-amber-200 bg-amber-50 text-amber-800'
                  : 'border-line bg-surface text-muted'
            }`}
            key={`${issue.field}-${index}`}
          >
            <span className="font-semibold">{formatSeverity(issue.severity)}:</span> {issue.message}
            {issue.suggestion ? <span className="block text-xs opacity-80">{issue.suggestion}</span> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

function formatSeverity(severity: ProductValidationIssue['severity']): string {
  if (severity === 'error') return 'Cần sửa';
  if (severity === 'warning') return 'Cần kiểm tra';
  return 'Gợi ý';
}
