import { useEffect } from 'react';
import { useKinSocket } from '../hooks/useKinSocket';

export default function DeviceTracker({ device, onUpdate, onAlert }) {
    const { lastLocation, status, deviceStatus } = useKinSocket(device.device_id, onAlert);

    useEffect(() => {
        onUpdate(device.device_id, lastLocation, status, deviceStatus);
    }, [device.device_id, lastLocation, status, deviceStatus, onUpdate]);

    return null;
}
