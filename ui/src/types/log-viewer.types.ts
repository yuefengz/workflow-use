export interface LogViewerProps {
  taskId: string | null;
  initialPosition: number;
  onStatusChange?: (status: string) => void;
  onComplete?: (result: any) => void;
  onError?: (error: string) => void;
  onCancel?: () => void;
  onClose?: () => void;
}