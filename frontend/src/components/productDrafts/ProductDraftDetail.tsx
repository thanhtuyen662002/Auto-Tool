import { useEffect, useMemo, useState } from 'react';
import type {
  CreateProjectFromDraftRequest,
  ProductDraft,
  ProductDraftStatus,
  ProductInfoNormalized,
  ProductSpec,
  ProjectListItem,
  ShopeeExtractorDebugReport,
} from '../../types/project';
import TextArea from '../TextArea';
import TextInput from '../TextInput';
import NumberInput from '../NumberInput';
import ProductAssetSelector from '../productAssets/ProductAssetSelector';
import PathInput from '../PathInput';

interface ProductDraftDetailProps {
  draft: ProductDraft;
  projects: ProjectListItem[];
  saving: boolean;
  onSave: (payload: {
    normalized_product: ProductInfoNormalized;
    status: ProductDraftStatus;
    user_note: string | null;
  }) => Promise<void>;
  onApplyToProject: (projectId: string, selectedAssetIds: string[]) => Promise<void>;
  onCreateProject: (payload: CreateProjectFromDraftRequest) => Promise<void>;
  onArchive: () => Promise<void>;
}

const EMPTY_PRODUCT: ProductInfoNormalized = {
  name: '',
  brand: '',
  description: '',
  features: [],
  specs: [],
  cta: 'Xem chi tiet san pham ngay',
  industry_preset_id: 'general_product',
  hashtag_suggestions: [],
  warnings: [],
  missing_fields: [],
  confidence_score: 0,
};

export default function ProductDraftDetail({
  draft,
  projects,
  saving,
  onSave,
  onApplyToProject,
  onCreateProject,
  onArchive,
}: ProductDraftDetailProps) {
  const [product, setProduct] = useState<ProductInfoNormalized>(() => draft.normalized_product ?? EMPTY_PRODUCT);
  const [status, setStatus] = useState<ProductDraftStatus>(draft.status);
  const [userNote, setUserNote] = useState(draft.user_note ?? '');
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [projectName, setProjectName] = useState(() => slugify(draft.title));
  const [sourceFolder, setSourceFolder] = useState('');
  const [outputFolder, setOutputFolder] = useState('examples/outputs');
  const [outputCount, setOutputCount] = useState(3);
  const [duration, setDuration] = useState(12);
  const [showRaw, setShowRaw] = useState(false);
  const [selectedAssetIds, setSelectedAssetIds] = useState<string[]>([]);

  useEffect(() => {
    setProduct(draft.normalized_product ?? EMPTY_PRODUCT);
    setStatus(draft.status);
    setUserNote(draft.user_note ?? '');
    setProjectName(slugify(draft.title));
    setSelectedAssetIds([]);
  }, [draft]);

  const rawJson = useMemo(
    () =>
      JSON.stringify(
        {
          raw_input: draft.raw_input,
          structured_data: draft.structured_data,
          extractor_debug: draft.extractor_debug,
        },
        null,
        2,
      ),
    [draft],
  );

  const updateProduct = (patch: Partial<ProductInfoNormalized>) => setProduct((current) => ({ ...current, ...patch }));
  const updateSpec = (index: number, patch: Partial<ProductSpec>) => {
    updateProduct({
      specs: (product.specs ?? []).map((spec, specIndex) => (specIndex === index ? { ...spec, ...patch } : spec)),
    });
  };

  return (
    <section className="space-y-5">
      <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-ink">{draft.title}</h2>
            <p className="mt-1 text-sm text-muted">
              Source: {draft.source.source_name ?? 'manual'} · Imported: {formatDate(draft.source.imported_at)}
            </p>
            {draft.source.source_url ? (
              <a className="mt-2 inline-block text-sm font-semibold text-brand" href={draft.source.source_url} rel="noreferrer" target="_blank">
                Open Source
              </a>
            ) : null}
          </div>
          <span className="rounded-md bg-surface px-3 py-1 text-xs font-semibold uppercase text-muted">{draft.status}</span>
        </div>
      </div>

      <ExtractionQuality report={draft.extractor_debug} />

      <ProductAssetSelector draftId={draft.id} onSelectionChange={setSelectedAssetIds} />

      <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-ink">Thông tin sản phẩm chuẩn hóa</h3>
            <p className="mt-1 text-xs text-muted">Xem xét và chỉnh sửa trước khi áp dụng bản nháp này vào dự án.</p>
          </div>
          <div className="flex items-center gap-2">
            <select
              className="rounded-md border border-line bg-white px-3 py-2 text-sm"
              value={status}
              onChange={(event) => setStatus(event.target.value as ProductDraftStatus)}
            >
              <option value="new">Mới</option>
              <option value="reviewed">Đã xem xét</option>
              <option value="applied">Đã áp dụng</option>
              <option value="archived">Đã lưu trữ</option>
            </select>
            <button
              className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
              type="button"
              disabled={saving}
              onClick={() => onSave({ normalized_product: product, status, user_note: userNote || null })}
            >
              {saving ? 'Đang lưu...' : 'Lưu Thay đổi'}
            </button>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <TextInput label="Tên sản phẩm" value={product.name} onChange={(name) => updateProduct({ name })} />
          <TextInput label="Thương hiệu" value={product.brand ?? ''} onChange={(brand) => updateProduct({ brand })} />
        </div>
        <div className="mt-4">
          <TextArea
            label="Mô tả sản phẩm"
            value={product.description}
            rows={4}
            onChange={(description) => updateProduct({ description })}
          />
        </div>
        <div className="mt-4">
          <TextArea
            label="Đặc tính nổi bật"
            value={product.features.join('\n')}
            rows={5}
            onChange={(value) =>
              updateProduct({
                features: value
                  .split('\n')
                  .map((item) => item.trim())
                  .filter(Boolean),
              })
            }
          />
        </div>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <TextInput label="Kêu gọi hành động (CTA)" value={product.cta} onChange={(cta) => updateProduct({ cta })} />
          <TextInput
            label="Mẫu cấu hình ngành hàng"
            value={product.industry_preset_id ?? ''}
            onChange={(industry_preset_id) => updateProduct({ industry_preset_id })}
          />
        </div>
        <div className="mt-4">
          <TextArea
            label="Hashtags"
            value={product.hashtag_suggestions.join('\n')}
            rows={3}
            onChange={(value) =>
              updateProduct({
                hashtag_suggestions: value
                  .split('\n')
                  .map((item) => item.trim())
                  .filter(Boolean),
              })
            }
          />
        </div>

        <div className="mt-5 rounded-md border border-line bg-surface/60 p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h4 className="text-sm font-semibold text-ink">Thông số kỹ thuật</h4>
            <button
              className="rounded-md border border-line bg-white px-3 py-2 text-xs font-semibold text-ink hover:border-brand"
              type="button"
              onClick={() => updateProduct({ specs: [...(product.specs ?? []), { name: '', value: '' }] })}
            >
              + Thêm thông số
            </button>
          </div>
          <div className="space-y-3">
            {(product.specs ?? []).map((spec, index) => (
              <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]" key={`${spec.name}-${index}`}>
                <TextInput label="Tên thông số" value={spec.name} onChange={(name) => updateSpec(index, { name })} />
                <TextInput label="Giá trị" value={spec.value} onChange={(value) => updateSpec(index, { value })} />
                <button
                  className="h-10 self-end rounded-md border border-line bg-white px-3 text-xs font-semibold text-red-600 hover:border-red-400"
                  type="button"
                  onClick={() => updateProduct({ specs: product.specs.filter((_, specIndex) => specIndex !== index) })}
                >
                  Xóa
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-4">
          <TextArea label="Ghi chú cá nhân" value={userNote} rows={3} onChange={setUserNote} />
        </div>
      </div>

      <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
        <h3 className="text-base font-semibold text-ink">Các lỗi phát hiện</h3>
        {draft.validation_issues.length ? (
          <ul className="mt-3 space-y-2 text-sm">
            {draft.validation_issues.map((issue, index) => (
              <li className="rounded-md bg-surface px-3 py-2" key={`${issue.field}-${index}`}>
                <span className="font-semibold capitalize">{issue.severity}</span>: {issue.message}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-muted">Không có lỗi xác thực nào.</p>
        )}
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
          <h3 className="text-base font-semibold text-ink">Áp dụng vào Dự án Hiện có</h3>
          <div className="mt-3 flex gap-3">
            <select
              className="min-w-0 flex-1 rounded-md border border-line bg-white px-3 py-2 text-sm"
              value={selectedProjectId}
              onChange={(event) => setSelectedProjectId(event.target.value)}
            >
              <option value="">Chọn dự án</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.project_name}
                </option>
              ))}
            </select>
            <button
              className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
              type="button"
              disabled={!selectedProjectId || saving}
              onClick={() => onApplyToProject(selectedProjectId, selectedAssetIds)}
            >
              Áp dụng
            </button>
          </div>
        </div>

        <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
          <h3 className="text-base font-semibold text-ink">Tạo Dự án Mới từ Bản nháp</h3>
          <div className="mt-3 grid gap-3">
            <TextInput label="Tên dự án" value={projectName} onChange={setProjectName} />
            <PathInput label="Thư mục video nguồn" value={sourceFolder} onChange={setSourceFolder} />
            <PathInput label="Thư mục đầu ra" value={outputFolder} onChange={setOutputFolder} />
            <div className="grid gap-3 sm:grid-cols-2">
              <NumberInput label="Số lượng video kết quả" value={outputCount} min={1} onChange={setOutputCount} />
              <NumberInput label="Thời lượng video (giây)" value={duration} min={3} onChange={setDuration} />
            </div>
            <button
              className="w-fit rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
              type="button"
              disabled={!projectName || !sourceFolder || !outputFolder || saving}
              onClick={() =>
                onCreateProject({
                  project_name: projectName,
                  source_folder: sourceFolder,
                  output_folder: outputFolder,
                  render: { output_count: outputCount, duration },
                  attach_selected_assets: selectedAssetIds.length > 0,
                  selected_asset_ids: selectedAssetIds.length > 0 ? selectedAssetIds : null,
                })
              }
            >
              Tạo dự án
            </button>
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <button
            className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
            type="button"
            onClick={() => setShowRaw((value) => !value)}
          >
            {showRaw ? 'Ẩn dữ liệu thô' : 'Hiển thị dữ liệu thô'}
          </button>
          <button
            className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-red-600 hover:border-red-400"
            type="button"
            disabled={saving}
            onClick={onArchive}
          >
            Lưu trữ bản nháp
          </button>
        </div>
        {showRaw ? (
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <pre className="max-h-80 overflow-auto rounded-md bg-surface p-4 text-xs">{draft.raw_text || 'Không có dữ liệu thô.'}</pre>
            <pre className="max-h-80 overflow-auto rounded-md bg-surface p-4 text-xs">{rawJson}</pre>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function ExtractionQuality({ report }: { report?: ShopeeExtractorDebugReport | null }) {
  if (!report) {
    return (
      <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
        <h3 className="text-base font-semibold text-ink">Chất lượng Trích xuất</h3>
        <p className="mt-2 text-sm text-muted">Không có báo cáo trích xuất nào được đính kèm bản nháp này.</p>
      </div>
    );
  }

  const confidence = Math.round((report.overallConfidence || 0) * 100);
  const missingFields = report.fields.filter((field) => !field.valueFound);
  const lowConfidence = report.overallConfidence < 0.65;

  return (
    <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-ink">Chất lượng Trích xuất</h3>
          <p className="mt-1 text-xs text-muted">
            Loại trang: {report.pageType} · Ngày trích xuất: {formatDate(report.extractedAt)}
          </p>
        </div>
        <span className={`rounded-md px-3 py-1 text-sm font-semibold ${lowConfidence ? 'bg-amber-100 text-amber-800' : 'bg-green-100 text-green-800'}`}>
          {confidence}%
        </span>
      </div>

      {lowConfidence ? (
        <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Độ tin cậy trích xuất thấp. Hãy kiểm tra kỹ các trường thông tin trước khi tạo dự án.
        </p>
      ) : null}

      {report.warnings.length || missingFields.length ? (
        <ul className="mt-3 space-y-1 text-sm text-muted">
          {missingFields.map((field) => (
            <li key={`missing-${field.field}`}>Thiếu trường: {field.field}</li>
          ))}
          {report.warnings.map((warning, index) => (
            <li key={`warning-${index}`}>{warning}</li>
          ))}
        </ul>
      ) : null}

      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        {report.fields.map((field) => (
          <div className="rounded-md border border-line bg-surface/60 px-3 py-2 text-xs" key={field.field}>
            <div className="flex items-center justify-between gap-2">
              <span className="font-semibold text-ink">{field.field}</span>
              <span className={field.valueFound ? 'text-green-700' : 'text-red-600'}>
                {field.valueFound ? `${Math.round(field.confidence * 100)}%` : 'thiếu'}
              </span>
            </div>
            <div className="mt-1 text-muted">Phương pháp: {field.method}</div>
            {field.valuePreview ? <div className="mt-1 truncate text-ink">{field.valuePreview}</div> : null}
            {field.warnings.length ? <div className="mt-1 text-amber-700">{field.warnings.join('; ')}</div> : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function slugify(value: string): string {
  return (
    value
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '') || 'product-draft'
  );
}
