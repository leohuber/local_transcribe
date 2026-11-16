from local_transcribe.application.ports import InputDevices, Recorder
from local_transcribe.domain.recording import (
    DeviceSelectionError,
    InputDevice,
    InputLevel,
    RecordingRequest,
    RecordingResult,
)


class Recording:
    def __init__(self, devices: InputDevices, recorder: Recorder) -> None:
        self._devices = devices
        self._recorder = recorder

    def list_inputs(self) -> tuple[InputDevice, ...]:
        return self._devices.list_inputs()

    def record(self, request: RecordingRequest) -> RecordingResult:
        if request.first_device_id == request.second_device_id:
            raise DeviceSelectionError("Select two distinct input devices.")

        available = {device.id for device in self.list_inputs()}
        if request.first_device_id not in available:
            raise DeviceSelectionError(
                f"Input device {request.first_device_id} is unavailable."
            )
        if request.second_device_id not in available:
            raise DeviceSelectionError(
                f"Input device {request.second_device_id} is unavailable."
            )
        return self._recorder.record(request)

    def latest_levels(self) -> tuple[InputLevel, ...]:
        return self._recorder.latest_levels()

    def stop(self) -> None:
        self._recorder.stop()
