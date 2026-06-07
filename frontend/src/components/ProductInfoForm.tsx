import type { ProductSpec, ProjectConfig } from '../types/project';
import NumberInput from './NumberInput';
import TextArea from './TextArea';
import TextInput from './TextInput';

interface ProductInfoFormProps {
  config: ProjectConfig;
  onChange: (config: ProjectConfig) => void;
}

export default function ProductInfoForm({ config, onChange }: ProductInfoFormProps) {
  const update = (patch: Partial<ProjectConfig>) => onChange({ ...config, ...patch });
  const updateProduct = (patch: Partial<ProjectConfig['product']>) =>
    onChange({ ...config, product: { ...config.product, ...patch } });
  const updateRender = (patch: Partial<ProjectConfig['render']>) =>
    onChange({ ...config, render: { ...config.render, ...patch } });
  const specs = config.product.specs ?? [];

  const updateSpec = (index: number, patch: Partial<ProductSpec>) => {
    updateProduct({
      specs: specs.map((spec, specIndex) => (specIndex === index ? { ...spec, ...patch } : spec)),
    });
  };

  const addSpec = () => {
    updateProduct({ specs: [...specs, { name: '', value: '' }] });
  };

  const removeSpec = (index: number) => {
    updateProduct({ specs: specs.filter((_, specIndex) => specIndex !== index) });
  };

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <TextInput
          label="Tên dự án"
          value={config.project_name}
          required
          onChange={(project_name) => update({ project_name })}
        />
        <TextInput
          label="Thương hiệu"
          value={config.product.brand}
          onChange={(brand) => updateProduct({ brand })}
        />
      </div>

      <TextInput
        label="Đường dẫn thư mục video nguồn"
        value={config.source_folder}
        onChange={(source_folder) => update({ source_folder })}
      />
      <TextInput
        label="Đường dẫn thư mục đầu ra"
        value={config.output_folder}
        onChange={(output_folder) => update({ output_folder })}
      />

      <TextInput
        label="Tên sản phẩm"
        value={config.product.name}
        onChange={(name) => updateProduct({ name })}
      />
      <TextArea
        label="Mô tả"
        value={config.product.description}
        rows={3}
        onChange={(description) => updateProduct({ description })}
      />
      <TextArea
        label="Tính năng nổi bật"
        value={config.product.features.join('\n')}
        rows={5}
        onChange={(value) =>
          updateProduct({
            features: value
              .split('\n')
          })
        }
      />
      <TextInput label="CTA" value={config.product.cta} onChange={(cta) => updateProduct({ cta })} />

      <div className="rounded-md border border-line bg-surface/60 p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-ink">Thông số được cung cấp</h3>
            <p className="mt-1 text-xs text-muted">Chỉ nhập thông số chắc chắn đúng. Tool sẽ không tự bịa thêm.</p>
          </div>
          <button
            className="rounded-md border border-line bg-white px-3 py-2 text-xs font-semibold text-ink hover:border-brand"
            type="button"
            onClick={addSpec}
          >
            + Thêm thông số
          </button>
        </div>
        <div className="space-y-3">
          {specs.length === 0 ? (
            <p className="rounded-md border border-dashed border-line bg-white px-3 py-3 text-xs text-muted">
              Chưa có thông số. Có thể để trống nếu người dùng chưa cung cấp.
            </p>
          ) : null}
          {specs.map((spec, index) => (
            <div className="grid gap-3 sm:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)_auto]" key={index}>
              <TextInput
                label="Tên thông số"
                value={spec.name}
                onChange={(name) => updateSpec(index, { name })}
              />
              <TextInput
                label="Giá trị"
                value={spec.value}
                onChange={(value) => updateSpec(index, { value })}
              />
              <button
                className="h-10 self-end rounded-md border border-line bg-white px-3 text-xs font-semibold text-red-600 hover:border-red-400"
                type="button"
                onClick={() => removeSpec(index)}
              >
                Xóa
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <NumberInput
          label="Số lượng video"
          value={config.render.output_count}
          min={1}
          onChange={(output_count) => updateRender({ output_count })}
        />
        <NumberInput
          label="Thời lượng"
          value={config.render.duration}
          min={3}
          onChange={(duration) => updateRender({ duration })}
        />
        <TextInput
          label="Độ phân giải"
          value={config.render.resolution}
          onChange={(resolution) => updateRender({ resolution })}
        />
        <NumberInput
          label="FPS"
          value={config.render.fps}
          min={1}
          onChange={(fps) => updateRender({ fps })}
        />
      </div>
    </div>
  );
}
